from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csv_export import export_capture_csv, export_live_run_csv
from protocol import CaptureMetadata, CapturePoint, LiveStatus
from session_state import LiveRunRow


class CsvExportTests(unittest.TestCase):
    def test_export_live_run_csv(self) -> None:
        status = LiveStatus(
            timestamp_ms=1000,
            setpoint=600,
            feedback=580,
            error=20,
            p_term=16.0,
            i_term=2.0,
            d_term=-1.0,
            raw_output=17.0,
            pwm=90,
            direction=1,
            deadband=False,
            saturated=False,
            kp=0.8,
            ki=0.1,
            kd=0.05,
            controller_enabled=True,
            capture_state=0,
            capture_samples=300,
            capture_trigger_delta=25,
            capture_interval_ms=10,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "live.csv"
            export_live_run_csv(file_path, [LiveRunRow(elapsed_ms=0, status=status)])
            content = file_path.read_text(encoding="utf-8")

        self.assertIn("elapsed_ms,setpoint,feedback", content)
        self.assertIn("0,600,580,20", content)

    def test_export_capture_csv(self) -> None:
        point = CapturePoint(
            sample_index=0,
            timestamp_ms=1000,
            setpoint=620,
            feedback=590,
            error=30,
            p_term=24.0,
            i_term=2.0,
            d_term=-0.5,
            raw_output=25.5,
            pwm=120,
            direction=1,
        )
        metadata = CaptureMetadata(kp=0.8, ki=0.1, kd=0.05, samples=300, interval_ms=10, trigger_delta=25)

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "capture.csv"
            export_capture_csv(file_path, [point], metadata)
            content = file_path.read_text(encoding="utf-8")

        self.assertIn("kp=0.8", content)
        self.assertIn("sample,ms,setpoint,feedback", content)
        self.assertIn("0,1000,620,590,30", content)


if __name__ == "__main__":
    unittest.main()
