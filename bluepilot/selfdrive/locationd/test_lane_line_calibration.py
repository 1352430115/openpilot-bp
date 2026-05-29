import unittest

from cereal import messaging
from bluepilot.selfdrive.locationd.lane_line_calibration import lane_lines_valid


class TestLaneLineCalibration(unittest.TestCase):
  def _model(self, left_prob: float, right_prob: float):
    msg = messaging.new_message('modelV2')
    msg.modelV2.laneLineProbs = [0.0, left_prob, right_prob, 0.0]
    return msg.modelV2

  def test_requires_both_lane_lines(self):
    self.assertFalse(lane_lines_valid(self._model(0.4, 0.9)))
    self.assertFalse(lane_lines_valid(self._model(0.9, 0.4)))
    self.assertTrue(lane_lines_valid(self._model(0.6, 0.7)))


if __name__ == "__main__":
  unittest.main()
