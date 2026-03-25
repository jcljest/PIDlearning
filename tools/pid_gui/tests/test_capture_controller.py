from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from capture_controller import CaptureController
from protocol import LiveStatus
from session_state import LiveRunRow, SessionState


def make_status(timestamp_ms: int, setpoint: int) -> LiveStatus:
    return LiveStatus(
        timestamp_ms=timestamp_ms,
        setpoint=setpoint,
        feedback=setpoint - 10,
        error=10,
        p_term=8.0,
        i_term=1.0,
        d_term=0.0,
        raw_output=9.0,
        pwm=80,
        direction=1,
        deadband=False,
        saturated=False,
        kp=0.8,
        ki=0.1,
        kd=0.0,
        controller_enabled=True,
        capture_state=0,
        capture_samples=300,
        capture_trigger_delta=25,
        capture_interval_ms=10,
    )


class CaptureControllerTests(unittest.TestCase):
    def test_arm_then_trigger_and_record(self) -> None:
        state = SessionState()
        controller = CaptureController(state)

        messages = controller.arm(baseline_setpoint=500, trigger_delta=20)
        self.assertEqual(state.live_mode, "armed")
        self.assertTrue(messages)

        controller.consume_status(make_status(1000, 510), trigger_delta=20)
        self.assertEqual(state.live_mode, "armed")

        controller.consume_status(make_status(1100, 525), trigger_delta=20)
        self.assertEqual(state.live_mode, "recording")
        self.assertEqual(len(state.live_run_rows), 1)
        self.assertEqual(state.live_run_rows[0].elapsed_ms, 0)

        controller.consume_status(make_status(1250, 530), trigger_delta=20)
        self.assertEqual(len(state.live_run_rows), 2)
        self.assertEqual(state.live_capture_duration_ms, 150)

    def test_stop_after_recording_marks_stopped(self) -> None:
        state = SessionState(live_mode="recording")
        state.live_run_rows.append(LiveRunRow(elapsed_ms=0, status=make_status(1000, 500)))
        controller = CaptureController(state)

        messages = controller.stop("Stopped.")

        self.assertEqual(state.live_mode, "stopped")
        self.assertEqual(messages, ["Stopped."])


if __name__ == "__main__":
    unittest.main()
