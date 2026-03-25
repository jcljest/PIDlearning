from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LiveStatus:
    timestamp_ms: int
    setpoint: int
    feedback: int
    error: int
    p_term: float
    i_term: float
    d_term: float
    raw_output: float
    pwm: int
    direction: int
    deadband: bool
    saturated: bool
    kp: float
    ki: float
    kd: float
    controller_enabled: bool
    capture_state: int
    capture_samples: int
    capture_trigger_delta: int
    capture_interval_ms: int


@dataclass
class CaptureMetadata:
    kp: float
    ki: float
    kd: float
    samples: int
    interval_ms: int
    trigger_delta: int


@dataclass
class CapturePoint:
    sample_index: int
    timestamp_ms: int
    setpoint: int
    feedback: int
    error: int
    p_term: float
    i_term: float
    d_term: float
    raw_output: float
    pwm: int
    direction: int


def capture_state_name(state: int) -> str:
    if state == 1:
        return "armed"
    if state == 2:
        return "capturing"
    return "idle"


def parse_status_line(line: str) -> Optional[LiveStatus]:
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 21 or parts[0] != "status":
        return None

    try:
        return LiveStatus(
            timestamp_ms=int(parts[1]),
            setpoint=int(parts[2]),
            feedback=int(parts[3]),
            error=int(parts[4]),
            p_term=float(parts[5]),
            i_term=float(parts[6]),
            d_term=float(parts[7]),
            raw_output=float(parts[8]),
            pwm=int(parts[9]),
            direction=int(parts[10]),
            deadband=parts[11] == "1",
            saturated=parts[12] == "1",
            kp=float(parts[13]),
            ki=float(parts[14]),
            kd=float(parts[15]),
            controller_enabled=parts[16] == "1",
            capture_state=int(parts[17]),
            capture_samples=int(parts[18]),
            capture_trigger_delta=int(parts[19]),
            capture_interval_ms=int(parts[20]),
        )
    except ValueError:
        return None


def parse_capture_metadata(line: str) -> Optional[CaptureMetadata]:
    if not line.startswith("# kp="):
        return None

    values = {}
    for part in line[2:].split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        values[key.strip()] = value.strip()

    try:
        return CaptureMetadata(
            kp=float(values["kp"]),
            ki=float(values["ki"]),
            kd=float(values["kd"]),
            samples=int(values["samples"]),
            interval_ms=int(values["interval_ms"]),
            trigger_delta=int(values["trigger_delta"]),
        )
    except (KeyError, ValueError):
        return None


def parse_capture_point(line: str) -> Optional[CapturePoint]:
    if not line or not line[0].isdigit():
        return None

    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 11:
        return None

    try:
        return CapturePoint(
            sample_index=int(parts[0]),
            timestamp_ms=int(parts[1]),
            setpoint=int(parts[2]),
            feedback=int(parts[3]),
            error=int(parts[4]),
            p_term=float(parts[5]),
            i_term=float(parts[6]),
            d_term=float(parts[7]),
            raw_output=float(parts[8]),
            pwm=int(parts[9]),
            direction=int(parts[10]),
        )
    except ValueError:
        return None
