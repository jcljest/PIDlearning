from __future__ import annotations

from typing import Optional

import serial
from serial.tools import list_ports


def available_ports() -> list[str]:
    return [port.device for port in list_ports.comports()]


class SerialClient:
    def __init__(self) -> None:
        self._serial_port: Optional[serial.Serial] = None
        self._read_buffer = bytearray()

    @property
    def is_open(self) -> bool:
        return bool(self._serial_port and self._serial_port.is_open)

    @property
    def port_name(self) -> str:
        if self._serial_port and self._serial_port.is_open:
            return str(self._serial_port.port)
        return "closed"

    def connect(self, port: str, baudrate: int = 115200) -> None:
        self._serial_port = serial.Serial(port=port, baudrate=baudrate, timeout=0)
        self._read_buffer.clear()

    def disconnect(self) -> None:
        if self._serial_port and self._serial_port.is_open:
            self._serial_port.close()
        self._serial_port = None
        self._read_buffer.clear()

    def send_line(self, line: str) -> None:
        if not self._serial_port or not self._serial_port.is_open:
            raise RuntimeError("Serial port is not open.")
        self._serial_port.write((line.strip() + "\n").encode("ascii"))

    def read_available_lines(self) -> list[str]:
        if not self._serial_port or not self._serial_port.is_open:
            return []

        waiting = self._serial_port.in_waiting
        if waiting <= 0:
            return []

        self._read_buffer.extend(self._serial_port.read(waiting))

        lines: list[str] = []
        while b"\n" in self._read_buffer:
            raw_line, _, remainder = self._read_buffer.partition(b"\n")
            self._read_buffer = bytearray(remainder)
            decoded = raw_line.decode("utf-8", errors="replace").strip()
            if decoded:
                lines.append(decoded)

        return lines
