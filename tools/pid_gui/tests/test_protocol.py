from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from protocol import parse_capture_metadata, parse_capture_point, parse_status_line


class ProtocolTests(unittest.TestCase):
    def test_parse_status_line(self) -> None:
        line = "status,123,600,580,20,16.0,2.0,-1.0,17.0,90,1,0,0,0.8,0.1,0.05,1,0,300,25,10"
        status = parse_status_line(line)

        self.assertIsNotNone(status)
        assert status is not None
        self.assertEqual(status.timestamp_ms, 123)
        self.assertEqual(status.setpoint, 600)
        self.assertEqual(status.feedback, 580)
        self.assertAlmostEqual(status.kp, 0.8)
        self.assertTrue(status.controller_enabled)

    def test_parse_capture_metadata(self) -> None:
        line = "# kp=0.8000,ki=0.1000,kd=0.0500,samples=300,interval_ms=10,trigger_delta=25"
        metadata = parse_capture_metadata(line)

        self.assertIsNotNone(metadata)
        assert metadata is not None
        self.assertEqual(metadata.samples, 300)
        self.assertEqual(metadata.trigger_delta, 25)

    def test_parse_capture_point(self) -> None:
        line = "12,500,620,590,30,24.0,2.0,-0.5,25.5,120,1"
        point = parse_capture_point(line)

        self.assertIsNotNone(point)
        assert point is not None
        self.assertEqual(point.sample_index, 12)
        self.assertEqual(point.pwm, 120)


if __name__ == "__main__":
    unittest.main()
