from __future__ import annotations

import csv
from pathlib import Path

from protocol import CaptureMetadata, CapturePoint
from session_state import LiveRunRow


def export_live_run_csv(file_path: str | Path, live_run_rows: list[LiveRunRow]) -> None:
    path = Path(file_path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "elapsed_ms",
                "setpoint",
                "feedback",
                "error",
                "p_term",
                "i_term",
                "d_term",
                "raw_output",
                "pwm",
                "direction",
                "kp",
                "ki",
                "kd",
            ]
        )

        for row in live_run_rows:
            status = row.status
            writer.writerow(
                [
                    row.elapsed_ms,
                    status.setpoint,
                    status.feedback,
                    status.error,
                    status.p_term,
                    status.i_term,
                    status.d_term,
                    status.raw_output,
                    status.pwm,
                    status.direction,
                    status.kp,
                    status.ki,
                    status.kd,
                ]
            )


def export_capture_csv(
    file_path: str | Path,
    capture_points: list[CapturePoint],
    capture_metadata: CaptureMetadata | None,
) -> None:
    path = Path(file_path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)

        if capture_metadata is not None:
            writer.writerow(
                [
                    "#",
                    f"kp={capture_metadata.kp}",
                    f"ki={capture_metadata.ki}",
                    f"kd={capture_metadata.kd}",
                    f"samples={capture_metadata.samples}",
                    f"interval_ms={capture_metadata.interval_ms}",
                    f"trigger_delta={capture_metadata.trigger_delta}",
                ]
            )

        writer.writerow(
            [
                "sample",
                "ms",
                "setpoint",
                "feedback",
                "error",
                "p_term",
                "i_term",
                "d_term",
                "raw_output",
                "pwm",
                "direction",
            ]
        )

        for point in capture_points:
            writer.writerow(
                [
                    point.sample_index,
                    point.timestamp_ms,
                    point.setpoint,
                    point.feedback,
                    point.error,
                    point.p_term,
                    point.i_term,
                    point.d_term,
                    point.raw_output,
                    point.pwm,
                    point.direction,
                ]
            )


def export_session_csv(
    file_path: str | Path,
    live_run_rows: list[LiveRunRow],
    capture_points: list[CapturePoint],
    capture_metadata: CaptureMetadata | None,
) -> str:
    if live_run_rows:
        export_live_run_csv(file_path, live_run_rows)
        return "live_run"

    if capture_points:
        export_capture_csv(file_path, capture_points, capture_metadata)
        return "capture"

    raise ValueError("No run data is available.")
