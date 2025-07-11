#!/usr/bin/env python3
"""BluePilot dmonitoringd — uses relaxed DRIVER_MONITOR_SETTINGS_BP."""

import cereal.messaging as messaging
from bluepilot.monitoring.dm_settings_bp import DRIVER_MONITOR_SETTINGS_BP
from openpilot.common.params import Params
from openpilot.common.realtime import config_realtime_process
from openpilot.selfdrive.monitoring.helpers import DriverMonitoring
from openpilot.system.hardware import HARDWARE


def dmonitoringd_thread():
  config_realtime_process([0, 1, 2, 3], 5)

  params = Params()
  pm = messaging.PubMaster(['driverMonitoringState'])
  sm = messaging.SubMaster(['driverStateV2', 'liveCalibration', 'carState', 'selfdriveState', 'modelV2',
                            'carControl'], poll='driverStateV2')

  dm_settings = DRIVER_MONITOR_SETTINGS_BP(HARDWARE.get_device_type())
  DM = DriverMonitoring(
    rhd_saved=params.get_bool("IsRhdDetected"),
    settings=dm_settings,
    always_on=params.get_bool("AlwaysOnDM"),
  )
  demo_mode = False

  while True:
    sm.update()
    if not sm.updated['driverStateV2']:
      continue

    valid = sm.all_checks()
    if demo_mode and sm.valid['driverStateV2']:
      DM.run_step(sm, demo=demo_mode)
    elif valid:
      DM.run_step(sm, demo=demo_mode)

    dat = DM.get_state_packet(valid=valid)
    pm.send('driverMonitoringState', dat)

    if sm['driverStateV2'].frameId % 40 == 1:
      DM.always_on = params.get_bool("AlwaysOnDM")
      demo_mode = params.get_bool("IsDriverViewEnabled")

    if (sm['driverStateV2'].frameId % 6000 == 0 and not demo_mode and
        DM.wheelpos.prob_offseter.filtered_stat.n > DM.settings._WHEELPOS_FILTER_MIN_COUNT and
        DM.wheel_on_right == (DM.wheelpos.prob_offseter.filtered_stat.M > DM.settings._WHEELPOS_THRESHOLD)):
      params.put_bool_nonblocking("IsRhdDetected", DM.wheel_on_right)


def main():
  dmonitoringd_thread()


if __name__ == '__main__':
  main()
