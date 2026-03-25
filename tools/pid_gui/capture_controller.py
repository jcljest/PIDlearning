from __future__ import annotations

from protocol import LiveStatus
from session_state import LiveRunRow, SessionState


class CaptureController:
    def __init__(self, state: SessionState) -> None:
        self.state = state

    @property
    def live_state_label(self) -> str:
        return self.state.live_mode

    @property
    def run_button_text(self) -> str:
        if self.state.live_mode == "recording":
            return "Stop Run"
        if self.state.live_mode == "armed":
            return "Cancel Armed Run"
        return "Start Triggered Run"

    def arm(self, baseline_setpoint: int | None, trigger_delta: int) -> list[str]:
        self.state.live_mode = "armed"
        self.state.clear_live_run()
        self.state.live_trigger_baseline = baseline_setpoint

        if baseline_setpoint is None:
            return ["Live run armed. Waiting for the first status row to establish the trigger baseline."]

        return [
            f"Live run armed at setpoint {baseline_setpoint}. Waiting for trigger delta {trigger_delta}."
        ]

    def stop(self, reason: str) -> list[str]:
        if self.state.live_mode not in {"armed", "recording"}:
            return []

        self.state.live_mode = "stopped" if self.state.live_run_rows else "idle"
        self.state.live_trigger_baseline = None
        return [reason]

    def reset(self) -> None:
        self.state.live_mode = "idle"
        self.state.clear_live_run()

    def consume_status(self, status: LiveStatus, trigger_delta: int) -> list[str]:
        messages: list[str] = []

        if self.state.live_mode not in {"armed", "recording"}:
            return messages

        if self.state.live_mode == "armed":
            if self.state.live_trigger_baseline is None:
                self.state.live_trigger_baseline = status.setpoint
                messages.append(
                    f"Live run baseline set to {status.setpoint}. Waiting for trigger delta {trigger_delta}."
                )
                return messages

            if abs(status.setpoint - self.state.live_trigger_baseline) < trigger_delta:
                return messages

            self.state.live_mode = "recording"
            self.state.live_capture_start_ms = status.timestamp_ms
            self.state.live_capture_duration_ms = 0
            self.state.live_run_rows.clear()
            messages.append(
                f"Live run triggered at setpoint {status.setpoint} "
                f"(baseline {self.state.live_trigger_baseline}, delta {trigger_delta})."
            )

        if self.state.live_mode == "recording" and self.state.live_capture_start_ms is not None:
            elapsed_ms = max(0, status.timestamp_ms - self.state.live_capture_start_ms)
            self.state.live_capture_duration_ms = elapsed_ms
            self.state.live_run_rows.append(LiveRunRow(elapsed_ms=elapsed_ms, status=status))

        return messages
