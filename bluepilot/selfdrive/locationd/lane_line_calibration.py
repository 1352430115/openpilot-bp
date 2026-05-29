from openpilot.common.params import Params

LANE_LINE_PROB_THRESHOLD = 0.5


def lane_line_calibration_required(params: Params | None = None) -> bool:
  params = params or Params()
  try:
    return params.get_bool("LaneLineCalibrationRequired")
  except Exception:
    return False


def lane_lines_valid(model_v2) -> bool:
  probs = model_v2.laneLineProbs
  if len(probs) < 3:
    return False
  return probs[1] >= LANE_LINE_PROB_THRESHOLD and probs[2] >= LANE_LINE_PROB_THRESHOLD
