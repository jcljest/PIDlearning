from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from protocol import CaptureMetadata, CapturePoint, LiveStatus


@dataclass
class LiveRunRow:
    elapsed_ms: int
    status: LiveStatus


@dataclass
class SessionState:
    capture_active: bool = False
    last_status: Optional[LiveStatus] = None
    capture_metadata: Optional[CaptureMetadata] = None
    capture_points: list[CapturePoint] = field(default_factory=list)

    live_mode: str = "idle"
    live_capture_start_ms: Optional[int] = None
    live_trigger_baseline: Optional[int] = None
    live_capture_duration_ms: int = 0
    live_run_rows: list[LiveRunRow] = field(default_factory=list)

    tx_count: int = 0
    rx_count: int = 0
    status_count: int = 0
    capture_row_count: int = 0
    malformed_count: int = 0
    last_tx_timestamp: str = "-"
    last_rx_timestamp: str = "-"

    def reset_comm_counters(self) -> None:
        self.tx_count = 0
        self.rx_count = 0
        self.status_count = 0
        self.capture_row_count = 0
        self.malformed_count = 0
        self.last_tx_timestamp = "-"
        self.last_rx_timestamp = "-"

    def record_tx(self, timestamp: str) -> None:
        self.tx_count += 1
        self.last_tx_timestamp = timestamp

    def record_rx(self, timestamp: str) -> None:
        self.rx_count += 1
        self.last_rx_timestamp = timestamp

    def record_status(self) -> None:
        self.status_count += 1

    def record_capture_row(self) -> None:
        self.capture_row_count += 1

    def record_malformed(self) -> None:
        self.malformed_count += 1

    def clear_live_run(self) -> None:
        self.live_capture_start_ms = None
        self.live_trigger_baseline = None
        self.live_capture_duration_ms = 0
        self.live_run_rows.clear()
