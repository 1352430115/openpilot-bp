"""BluePilot driver monitoring policy — relaxed vs stock openpilot defaults."""

from openpilot.selfdrive.monitoring.helpers import DRIVER_MONITOR_SETTINGS
from openpilot.system.hardware import HARDWARE


class DRIVER_MONITOR_SETTINGS_BP(DRIVER_MONITOR_SETTINGS):
  """Less aggressive DM: more head movement allowed, longer grace before alerts."""

  def __init__(self, device_type=None):
    super().__init__(device_type or HARDWARE.get_device_type())

    # Longer timeouts before pre / prompt / terminal distraction alerts
    self._DISTRACTED_TIME = 14.0
    self._DISTRACTED_PRE_TIME_TILL_TERMINAL = 10.0
    self._DISTRACTED_PROMPT_TIME_TILL_TERMINAL = 7.0

    # Allow more pitch / yaw before counting as distracted (~30% vs stock)
    self._POSE_PITCH_THRESHOLD = 0.41
    self._POSE_PITCH_THRESHOLD_SLACK = 0.42
    self._POSE_PITCH_THRESHOLD_STRICT = self._POSE_PITCH_THRESHOLD
    self._POSE_YAW_THRESHOLD = 0.52
    self._POSE_YAW_THRESHOLD_SLACK = 0.65
    self._POSE_YAW_THRESHOLD_STRICT = self._POSE_YAW_THRESHOLD
    self._PITCH_NATURAL_THRESHOLD = 0.58

    self._BLINK_THRESHOLD = 0.90
    self._PHONE_THRESH = 0.55

    # Slower distraction filter (less twitchy at 20 Hz)
    self._DISTRACTED_FILTER_TS = 0.35

    # Hysteresis for awareness recovery / decay (stock: 0.37 / 0.63)
    self._ATTENTIVE_FILTER_THRESHOLD = 0.45
    self._DISTRACTED_FILTER_THRESHOLD = 0.72
