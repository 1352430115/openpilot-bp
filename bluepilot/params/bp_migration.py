from openpilot.common.params import Params, UnknownKeyName
from openpilot.common.swaglog import cloudlog


def run_bp_migration(params: Params) -> None:
  """BluePilot param migrations run once per manager start."""
  _ensure_first_install_calibration(params)


def _ensure_first_install_calibration(params: Params) -> None:
  """Force camera calibration on first BluePilot install.

  Fresh installs should enter calibration mode on the first drive. Clear any
  stale CalibrationParams and require visible lane lines before collecting samples.
  """
  try:
    params.check_key("LaneLineCalibrationRequired")
  except UnknownKeyName:
    return

  last_seen = params.get("BPLastSeenVersion") or ""
  if last_seen:
    return

  params.put_bool("LaneLineCalibrationRequired", True)
  try:
    params.remove("CalibrationParams")
  except UnknownKeyName:
    pass
  cloudlog.info("BluePilot first install: enabled lane-line calibration gate and cleared CalibrationParams")
