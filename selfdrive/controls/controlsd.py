#!/usr/bin/env python3
import math
from numbers import Number

from cereal import car, log
import cereal.messaging as messaging
from openpilot.common.constants import CV
from openpilot.common.params import Params
from openpilot.common.realtime import config_realtime_process, DT_CTRL, Priority, Ratekeeper
from openpilot.common.swaglog import cloudlog

from opendbc.car.car_helpers import interfaces
from opendbc.car.vehicle_model import VehicleModel
from openpilot.selfdrive.controls.lib.drive_helpers import clip_curvature
from openpilot.selfdrive.controls.lib.latcontrol import LatControl
from openpilot.selfdrive.controls.lib.latcontrol_pid import LatControlPID
from openpilot.selfdrive.controls.lib.latcontrol_angle import LatControlAngle, STEER_ANGLE_SATURATION_THRESHOLD
from openpilot.selfdrive.controls.lib.latcontrol_torque import LatControlTorque
from openpilot.selfdrive.controls.lib.longcontrol import LongControl
from openpilot.selfdrive.modeld.modeld import LAT_SMOOTH_SECONDS
from openpilot.selfdrive.locationd.helpers import PoseCalibrator, Pose

from openpilot.sunnypilot.selfdrive.controls.controlsd_ext import ControlsExt
from openpilot.sunnypilot.selfdrive.controls.lib.curvature_lead import apply_curvature_lead, apply_curvature_exit_lead
from openpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc import (
  FordFollowBarsDisplay, is_ford_auto_follow_gap,
)

State = log.SelfdriveState.OpenpilotState
LaneChangeState = log.LaneChangeState
LaneChangeDirection = log.LaneChangeDirection

ACTUATOR_FIELDS = tuple(car.CarControl.Actuators.schema.fields.keys())


class Controls(ControlsExt):
  def __init__(self) -> None:
    self.params = Params()
    cloudlog.info("controlsd is waiting for CarParams")
    self.CP = messaging.log_from_bytes(self.params.get("CarParams", block=True), car.CarParams)
    cloudlog.info("controlsd got CarParams")

    # Initialize sunnypilot controlsd extension and base model state
    ControlsExt.__init__(self, self.CP, self.params)

    self.CI = interfaces[self.CP.carFingerprint](self.CP, self.CP_SP)

    self.sm = messaging.SubMaster(['liveDelay', 'liveParameters', 'liveTorqueParameters', 'modelV2', 'selfdriveState',
                                   'liveCalibration', 'livePose', 'longitudinalPlan', 'lateralManeuverPlan', 'carState', 'carOutput',
                                   'driverMonitoringState', 'onroadEvents', 'driverAssistance', 'liveDelay'] + self.sm_services_ext,
                                  poll='selfdriveState')
    self.pm = messaging.PubMaster(['carControl', 'controlsState'] + self.pm_services_ext)

    self.steer_limited_by_safety = False
    self.curvature = 0.0
    self.desired_curvature = 0.0

    self.pose_calibrator = PoseCalibrator()
    self.calibrated_pose: Pose | None = None

    self.LoC = LongControl(self.CP, self.CP_SP)
    self.VM = VehicleModel(self.CP)
    self.LaC: LatControl
    if self.CP.steerControlType == car.CarParams.SteerControlType.angle:
      self.LaC = LatControlAngle(self.CP, self.CP_SP, self.CI, DT_CTRL)
    elif self.CP.lateralTuning.which() == 'pid':
      self.LaC = LatControlPID(self.CP, self.CP_SP, self.CI, DT_CTRL)
    elif self.CP.lateralTuning.which() == 'torque':
      self.LaC = LatControlTorque(self.CP, self.CP_SP, self.CI, DT_CTRL)

    self.LaC = ControlsExt.initialize_lateral_control(self, self.LaC, self.CI, DT_CTRL)
    self._ford_follow_bars = FordFollowBarsDisplay()

  def update(self):
    self.sm.update(15)
    if self.sm.updated["liveCalibration"]:
      self.pose_calibrator.feed_live_calib(self.sm['liveCalibration'])
    if self.sm.updated["livePose"]:
      device_pose = Pose.from_live_pose(self.sm['livePose'])
      self.calibrated_pose = self.pose_calibrator.build_calibrated_pose(device_pose)

  def state_control(self):
    CS = self.sm['carState']

    # Update VehicleModel
    lp = self.sm['liveParameters']
    x = max(lp.stiffnessFactor, 0.1)
    sr = max(lp.steerRatio, 0.1)
    self.VM.update_params(x, sr)

    steer_angle_without_offset = math.radians(CS.steeringAngleDeg - lp.angleOffsetDeg)
    self.curvature = -self.VM.calc_curvature(steer_angle_without_offset, CS.vEgo, lp.roll)

    # Update Torque Params
    if self.CP.lateralTuning.which() == 'torque':
      torque_params = self.sm['liveTorqueParameters']
      if self.sm.all_checks(['liveTorqueParameters']) and torque_params.useParams:
        self.LaC.update_live_torque_params(torque_params.latAccelFactorFiltered, torque_params.latAccelOffsetFiltered,
                                           torque_params.frictionCoefficientFiltered)

        self.LaC.extension.update_limits()

      self.LaC.extension.update_model_v2(self.sm['modelV2'])

      self.LaC.extension.update_lateral_lag(self.lat_delay)

    long_plan = self.sm['longitudinalPlan']
    model_v2 = self.sm['modelV2']

    CC = car.CarControl.new_message()
    CC.enabled = self.sm['selfdriveState'].enabled

    # Check which actuators can be enabled
    standstill = abs(CS.vEgo) <= max(self.CP.minSteerSpeed, 0.3) or CS.standstill

    # Get which state to use for active lateral control
    _lat_active = self.get_lat_active(self.sm)
    model_angle_deg = math.degrees(self.VM.get_steer_from_curvature(
      model_v2.action.desiredCurvature, CS.vEgo, lp.roll))
    _lat_active = self.apply_htd(_lat_active, self.sm, model_angle_deg)

    CC.latActive = _lat_active and not CS.steerFaultTemporary and not CS.steerFaultPermanent and \
                   (not standstill or self.CP.steerAtStandstill)
    CC.longActive = CC.enabled and not any(e.overrideLongitudinal for e in self.sm['onroadEvents']) and \
                    (self.CP.openpilotLongitudinalControl or not self.CP_SP.pcmCruiseSpeed)

    actuators = CC.actuators
    actuators.longControlState = self.LoC.long_control_state

    # Enable blinkers while lane changing
    if model_v2.meta.laneChangeState != LaneChangeState.off:
      CC.leftBlinker = model_v2.meta.laneChangeDirection == LaneChangeDirection.left
      CC.rightBlinker = model_v2.meta.laneChangeDirection == LaneChangeDirection.right

    if not CC.latActive:
      self.LaC.reset()
    if not CC.longActive:
      self.LoC.reset()

    # accel PID loop
    pid_accel_limits = self.CI.get_pid_accel_limits(self.CP, self.CP_SP, CS.vEgo, CS.vCruise * CV.KPH_TO_MS)
    personality = self.sm['selfdriveState'].personality
    actuators.accel = float(self.LoC.update(CC.longActive, CS, long_plan.aTarget, long_plan.shouldStop,
                                             pid_accel_limits, personality=personality))

    # Steering PID loop and lateral MPC
    # When lat inactive (incl. HTD pause): snap desired to current wheel curvature so
    # re-engage blends from actual angle — not a rate-limited leftover curve command.
    lat_delay = self.sm["liveDelay"].lateralDelay + LAT_SMOOTH_SECONDS
    if not CC.latActive:
      self.desired_curvature = float(self.curvature)
      curvature_limited = False
    else:
      if self.sm.valid['lateralManeuverPlan']:
        new_desired_curvature = self.sm['lateralManeuverPlan'].desiredCurvature
      else:
        new_desired_curvature = model_v2.action.desiredCurvature
        # Advance plan sampling when a sharp curve is predicted (no toggle).
        # Larger predicted |κ| → larger lead so curvature climbs earlier into the turn.
        new_desired_curvature = apply_curvature_lead(
          model_v2, CS.vEgo, new_desired_curvature, lat_delay,
        )
        new_desired_curvature = apply_curvature_exit_lead(
          model_v2, CS.vEgo, new_desired_curvature, lat_delay,
        )
      self.desired_curvature, curvature_limited = clip_curvature(
        CS.vEgo, self.desired_curvature, new_desired_curvature, lp.roll)

    actuators.curvature = self.desired_curvature
    steer, steeringAngleDeg, lac_log = self.LaC.update(CC.latActive, CS, self.VM, lp,
                                                       self.steer_limited_by_safety, self.desired_curvature,
                                                       self.calibrated_pose, curvature_limited, lat_delay)
    actuators.torque = float(steer)
    actuators.steeringAngleDeg = float(steeringAngleDeg)
    # ===================== HugDebug START（临时诊断，定位转弯贴线） =====================
    try:
      _mv2 = self.sm['modelV2']
      _ll  = _mv2.laneLines
      _probs = _mv2.laneLineProbs
      def _y(idx, k):
        try: return float(_ll[idx].y[k])
        except Exception: return float('nan')
      _k0 = 0
      _k8 = min(8, len(_ll[0].y) - 1)          # 中前瞻点（约对应 X_IDXS[8]，避开近点退化）
      _li0, _ri0 = _y(1, _k0), _y(2, _k0)      # 左内 / 右内 近点
      _li8, _ri8 = _y(1, _k8), _y(2, _k8)      # 左内 / 右内 中前瞻
      _pl, _pr   = float(_probs[1]), float(_probs[2])
      _c0, _hw0  = (_li0 + _ri0) / 2.0, (_ri0 - _li0) / 2.0
      _c8, _hw8  = (_li8 + _ri8) / 2.0, (_ri8 - _li8) / 2.0
      _off0, _off8 = -_c0, -_c8                 # 车相对车道中心的偏移（车≈y=0）
      _crossR0 = _ri0 < 0; _crossL0 = _li0 > 0  # 是否压过内线
      _hug0 = (abs(_off0) > 0.6 * _hw0) if _hw0 > 0.1 else False
      _lmp = self.sm.valid['lateralManeuverPlan']
      _msg = (f"HugDebug|vEgo={CS.vEgo:.2f}|steerAct={CS.steeringAngleDeg:.2f}|"
              f"curvAct={self.curvature:.5f}|"
              f"desModel={model_v2.action.desiredCurvature:.5f}|"
              f"desNew={new_desired_curvature:.5f}|desClip={self.desired_curvature:.5f}|"
              f"limited={curvature_limited}|cmdAng={steeringAngleDeg:.2f}|"
              f"roll={lp.roll:.4f}|angleOff={lp.angleOffsetDeg:.3f}|"
              f"sr={lp.steerRatio:.3f}|stiff={lp.stiffnessFactor:.3f}|"
              f"laneChg={model_v2.meta.laneChangeState}|lmp={_lmp}|"
              f"pL={_pl:.2f}|pR={_pr:.2f}|"
              f"li0={_li0:.2f}|ri0={_ri0:.2f}|c0={_c0:.2f}|hw0={_hw0:.2f}|off0={_off0:.2f}|"
              f"crossR0={_crossR0}|crossL0={_crossL0}|hug0={_hug0}|"
              f"li8={_li8:.2f}|ri8={_ri8:.2f}|c8={_c8:.2f}|hw8={_hw8:.2f}|off8={_off8:.2f}")
      cloudlog.warning(_msg)
      # 同时落盘，方便整段抓取（诊断完删掉本行及下面两行）
      with open('/tmp/hug_debug.log', 'a') as _f:
        _f.write(f"{CS.frame if hasattr(CS,'frame') else 0} {_msg}\n")
    except Exception as _e:
      cloudlog.warning(f"HugDebug|ERR {_e}")
    # ===================== HugDebug END =====================
    # Ensure no NaNs/Infs
    for p in ACTUATOR_FIELDS:
      attr = getattr(actuators, p)
      if not isinstance(attr, Number):
        continue

      if not math.isfinite(attr):
        cloudlog.error(f"actuators.{p} not finite {actuators.to_dict()}")
        setattr(actuators, p, 0.0)

    return CC, lac_log

  def publish(self, CC, lac_log):
    CS = self.sm['carState']

    # Orientation and angle rates can be useful for carcontroller
    # Only calibrated (car) frame is relevant for the carcontroller
    CC.currentCurvature = self.curvature
    if self.calibrated_pose is not None:
      CC.orientationNED = self.calibrated_pose.orientation.xyz.tolist()
      CC.angularVelocity = self.calibrated_pose.angular_velocity.xyz.tolist()

    CC.cruiseControl.override = CC.enabled and not CC.longActive and (self.CP.openpilotLongitudinalControl or not self.CP_SP.pcmCruiseSpeed)
    CC.cruiseControl.cancel = CS.cruiseState.enabled and (not CC.enabled or not self.CP.pcmCruise)
    CC.cruiseControl.resume = CC.enabled and CS.cruiseState.standstill and not self.sm['longitudinalPlan'].shouldStop

    hudControl = CC.hudControl
    hudControl.setSpeed = float(CS.vCruiseCluster * CV.KPH_TO_MS)
    hudControl.speedVisible = CC.enabled
    hudControl.lanesVisible = CC.enabled
    hudControl.leadVisible = self.sm['longitudinalPlan'].hasLead
    if is_ford_auto_follow_gap(self.params, self.CP):
      at_standstill = CS.standstill or CS.cruiseState.standstill
      hudControl.leadDistanceBars = self._ford_follow_bars.update(CS.vEgo, at_standstill)
    else:
      hudControl.leadDistanceBars = self.sm['selfdriveState'].personality.raw + 1
    hudControl.visualAlert = self.sm['selfdriveState'].alertHudVisual

    hudControl.rightLaneVisible = True
    hudControl.leftLaneVisible = True
    if self.sm.valid['driverAssistance']:
      hudControl.leftLaneDepart = self.sm['driverAssistance'].leftLaneDeparture
      hudControl.rightLaneDepart = self.sm['driverAssistance'].rightLaneDeparture

    if self.get_lat_active(self.sm):
      CO = self.sm['carOutput']
      if self.CP.steerControlType == car.CarParams.SteerControlType.angle:
        self.steer_limited_by_safety = abs(CC.actuators.steeringAngleDeg - CO.actuatorsOutput.steeringAngleDeg) > \
                                              STEER_ANGLE_SATURATION_THRESHOLD
      else:
        self.steer_limited_by_safety = abs(CC.actuators.torque - CO.actuatorsOutput.torque) > 1e-2

    # TODO: both controlsState and carControl valids should be set by
    #       sm.all_checks(), but this creates a circular dependency

    # controlsState
    dat = messaging.new_message('controlsState')
    dat.valid = CS.canValid
    cs = dat.controlsState

    cs.curvature = self.curvature
    cs.longitudinalPlanMonoTime = self.sm.logMonoTime['longitudinalPlan']
    cs.lateralPlanMonoTime = self.sm.logMonoTime['modelV2']
    cs.desiredCurvature = self.desired_curvature
    cs.longControlState = self.LoC.long_control_state
    cs.upAccelCmd = float(self.LoC.pid.p)
    cs.uiAccelCmd = float(self.LoC.pid.i)
    cs.ufAccelCmd = float(self.LoC.pid.f)
    cs.forceDecel = bool((self.sm['driverMonitoringState'].alertLevel == log.DriverMonitoringState.AlertLevel.three) or
                         (self.sm['selfdriveState'].state == State.softDisabling))

    lat_tuning = self.CP.lateralTuning.which()
    if self.CP.steerControlType == car.CarParams.SteerControlType.angle:
      cs.lateralControlState.angleState = lac_log
    elif lat_tuning == 'pid':
      cs.lateralControlState.pidState = lac_log
    elif lat_tuning == 'torque':
      cs.lateralControlState.torqueState = lac_log

    self.pm.send('controlsState', dat)

    # carControl
    cc_send = messaging.new_message('carControl')
    cc_send.valid = CS.canValid
    cc_send.carControl = CC
    self.pm.send('carControl', cc_send)

  def run(self):
    rk = Ratekeeper(100, print_delay_threshold=None)
    while True:
      self.update()
      CC, lac_log = self.state_control()
      self.publish(CC, lac_log)
      self.get_params_sp(self.sm)
      self.run_ext(self.sm, self.pm)
      rk.monitor_time()


def main():
  config_realtime_process(4, Priority.CTRL_HIGH)
  controls = Controls()
  controls.run()


if __name__ == "__main__":
  main()
