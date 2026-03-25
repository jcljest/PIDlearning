from __future__ import annotations

import sys
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from serial_client import SerialClient


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.port = kwargs.get("port", "COM_FAKE")
        self.written_data = b""
        self._read_buffer = b""

    def write(self, data: bytes) -> None:
        self.written_data += data

    def read(self, n: int) -> bytes:
        chunk = self._read_buffer[:n]
        self._read_buffer = self._read_buffer[n:]
        return chunk

    @property
    def in_waiting(self) -> int:
        return len(self._read_buffer)

    def close(self) -> None:
        self.is_open = False

    def inject_data(self, data: bytes) -> None:
        self._read_buffer += data


class SerialClientTests(unittest.TestCase):
    @patch("serial_client.serial.Serial", new=FakeSerial)
    def test_connect_and_disconnect(self) -> None:
        client = SerialClient()
        client.connect("COM_TEST")

        self.assertTrue(client.is_open)
        self.assertEqual(client.port_name, "COM_TEST")
        self.assertIsNotNone(client._serial_port)

        client.disconnect()

        self.assertFalse(client.is_open)
        self.assertEqual(client.port_name, "closed")
        self.assertIsNone(client._serial_port)

    @patch("serial_client.serial.Serial", new=FakeSerial)
    def test_send_line(self) -> None:
        client = SerialClient()
        client.connect("COM_TEST")

        assert client._serial_port is not None
        client.send_line("statuscsv")

        self.assertEqual(client._serial_port.written_data, b"statuscsv\n")

    @patch("serial_client.serial.Serial", new=FakeSerial)
    def test_read_single_line(self) -> None:
        client = SerialClient()
        client.connect("COM_TEST")

        assert client._serial_port is not None
        client._serial_port.inject_data(b"status,1,2,3\n")

        lines = client.read_available_lines()

        self.assertEqual(lines, ["status,1,2,3"])

    @patch("serial_client.serial.Serial", new=FakeSerial)
    def test_read_partial_line(self) -> None:
        client = SerialClient()
        client.connect("COM_TEST")

        assert client._serial_port is not None
        client._serial_port.inject_data(b"status,1,2")
        lines = client.read_available_lines()
        self.assertEqual(lines, [])

        client._serial_port.inject_data(b",3\n")
        lines = client.read_available_lines()
        self.assertEqual(lines, ["status,1,2,3"])

    @patch("serial_client.serial.Serial", new=FakeSerial)
    def test_multiple_lines(self) -> None:
        client = SerialClient()
        client.connect("COM_TEST")

        assert client._serial_port is not None
        client._serial_port.inject_data(b"a\nb\nc\n")

        lines = client.read_available_lines()

        self.assertEqual(lines, ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()