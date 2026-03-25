from __future__ import annotations

import csv
import time
from collections import deque
from pathlib import Path
from typing import Optional

import pyqtgraph as pg
import serial
from serial import SerialException
from serial.tools import list_ports
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from protocol import (
    CaptureMetadata,
    CapturePoint,
    LiveStatus,
    capture_state_name,
    parse_capture_metadata,
    parse_capture_point,
    parse_status_line,
)


class PidTuningWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PID Capture Console")
        self.resize(1460, 920)

        self.serial_port: Optional[serial.Serial] = None
        self.read_buffer = bytearray()
        self.capture_active = False
        self.last_status: Optional[LiveStatus] = None
        self.capture_metadata: Optional[CaptureMetadata] = None
        self.capture_points: list[CapturePoint] = []
        self.tx_count = 0
        self.rx_count = 0
        self.status_count = 0
        self.capture_row_count = 0
        self.malformed_count = 0
        self.last_tx_timestamp = "-"
        self.last_rx_timestamp = "-"

        self.live_time = deque(maxlen=500)
        self.live_setpoint = deque(maxlen=500)
        self.live_feedback = deque(maxlen=500)
        self.live_output = deque(maxlen=500)
        self.live_pwm = deque(maxlen=500)

        self._build_ui()
        self._apply_style()
        self.refresh_ports()

        self.serial_timer = QTimer(self)
        self.serial_timer.timeout.connect(self.poll_serial)
        self.serial_timer.start(25)

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.request_status_update)
        self.status_timer.start(250)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)

        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(18, 18, 18, 18)
        outer_layout.setSpacing(12)

        title = QLabel("PID Live Tuning + Capture")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Tune gains, arm captures, and inspect oscillations without reflashing.")
        subtitle.setObjectName("subtitleLabel")

        outer_layout.addWidget(title)
        outer_layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Horizontal)
        outer_layout.addWidget(splitter, 1)

        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(12)

        control_layout.addWidget(self._build_connection_group())
        control_layout.addWidget(self._build_pid_group())
        control_layout.addWidget(self._build_capture_group())
        control_layout.addWidget(self._build_status_group())
        control_layout.addWidget(self._build_console_group(), 1)

        plots_panel = QWidget()
        plots_layout = QVBoxLayout(plots_panel)
        plots_layout.setContentsMargins(0, 0, 0, 0)
        plots_layout.setSpacing(12)

        self.live_plot = self._create_plot(
            "Live Position",
            "Time (s)",
            "Counts",
            [("Setpoint", "#db6a32"), ("Feedback", "#1b6b72")],
        )
        self.live_drive_plot = self._create_plot(
            "Live Drive",
            "Time (s)",
            "Drive",
            [("Raw Output", "#5b4db2"), ("PWM", "#a23a72")],
        )
        self.capture_plot = self._create_plot(
            "Capture Oscillation",
            "Time (s)",
            "Counts",
            [("Setpoint", "#db6a32"), ("Feedback", "#1b6b72")],
        )

        plots_layout.addWidget(self.live_plot["widget"], 1)
        plots_layout.addWidget(self.live_drive_plot["widget"], 1)
        plots_layout.addWidget(self.capture_plot["widget"], 1)

        splitter.addWidget(control_panel)
        splitter.addWidget(plots_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 1040])

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("Connection")
        layout = QGridLayout(group)

        self.port_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        self.connect_button = QPushButton("Connect")
        self.clear_trace_button = QPushButton("Clear Trace")
        self.trace_auto_checkbox = QCheckBox("Show auto poll traffic")
        self.trace_auto_checkbox.setChecked(False)

        self.refresh_button.clicked.connect(self.refresh_ports)
        self.connect_button.clicked.connect(self.toggle_connection)
        self.clear_trace_button.clicked.connect(self.clear_trace)

        layout.addWidget(QLabel("Serial Port"), 0, 0)
        layout.addWidget(self.port_combo, 0, 1)
        layout.addWidget(self.refresh_button, 0, 2)
        layout.addWidget(self.connect_button, 1, 0, 1, 3)
        layout.addWidget(self.trace_auto_checkbox, 2, 0, 1, 2)
        layout.addWidget(self.clear_trace_button, 2, 2)
        return group

    def _build_pid_group(self) -> QGroupBox:
        group = QGroupBox("PID")
        layout = QFormLayout(group)

        self.kp_spin = self._make_gain_spin()
        self.ki_spin = self._make_gain_spin()
        self.kd_spin = self._make_gain_spin()

        self.apply_pid_button = QPushButton("Apply Gains")
        self.run_button = QPushButton("Run")
        self.stop_button = QPushButton("Stop")
        self.reset_button = QPushButton("Reset PID")

        self.apply_pid_button.clicked.connect(self.apply_pid)
        self.run_button.clicked.connect(lambda: self.send_command("run"))
        self.stop_button.clicked.connect(lambda: self.send_command("stop"))
        self.reset_button.clicked.connect(lambda: self.send_command("reset"))

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addWidget(self.run_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.reset_button)

        layout.addRow("Kp", self.kp_spin)
        layout.addRow("Ki", self.ki_spin)
        layout.addRow("Kd", self.kd_spin)
        layout.addRow(self.apply_pid_button)
        layout.addRow(button_row)
        return group

    def _build_capture_group(self) -> QGroupBox:
        group = QGroupBox("Capture")
        layout = QFormLayout(group)

        self.capture_samples_spin = QSpinBox()
        self.capture_samples_spin.setRange(10, 10000)
        self.capture_samples_spin.setValue(300)

        self.capture_trigger_spin = QSpinBox()
        self.capture_trigger_spin.setRange(1, 1023)
        self.capture_trigger_spin.setValue(25)

        self.capture_interval_spin = QSpinBox()
        self.capture_interval_spin.setRange(1, 1000)
        self.capture_interval_spin.setValue(10)

        self.arm_button = QPushButton("Arm Triggered Capture")
        self.capture_now_button = QPushButton("Capture Now")
        self.cancel_button = QPushButton("Cancel")
        self.save_button = QPushButton("Save Capture CSV")

        self.arm_button.clicked.connect(self.arm_capture)
        self.capture_now_button.clicked.connect(self.start_capture_now)
        self.cancel_button.clicked.connect(lambda: self.send_command("cancel"))
        self.save_button.clicked.connect(self.save_capture_csv)

        button_row = QWidget()
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(8)
        button_layout.addWidget(self.capture_now_button)
        button_layout.addWidget(self.cancel_button)

        layout.addRow("Samples", self.capture_samples_spin)
        layout.addRow("Trigger Delta", self.capture_trigger_spin)
        layout.addRow("Interval ms", self.capture_interval_spin)
        layout.addRow(self.arm_button)
        layout.addRow(button_row)
        layout.addRow(self.save_button)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Status")
        layout = QGridLayout(group)

        self.connection_value = QLabel("disconnected")
        self.port_state_value = QLabel("closed")
        self.controller_value = QLabel("unknown")
        self.capture_value = QLabel("idle")
        self.setpoint_value = QLabel("-")
        self.feedback_value = QLabel("-")
        self.error_value = QLabel("-")
        self.output_value = QLabel("-")
        self.pwm_value = QLabel("-")
        self.last_tx_value = QLabel("-")
        self.last_rx_value = QLabel("-")
        self.tx_count_value = QLabel("0")
        self.rx_count_value = QLabel("0")
        self.status_count_value = QLabel("0")
        self.malformed_value = QLabel("0")

        labels = [
            ("Link", self.connection_value),
            ("Port", self.port_state_value),
            ("Controller", self.controller_value),
            ("Capture", self.capture_value),
            ("Setpoint", self.setpoint_value),
            ("Feedback", self.feedback_value),
            ("Error", self.error_value),
            ("Raw Output", self.output_value),
            ("PWM", self.pwm_value),
            ("Last TX", self.last_tx_value),
            ("Last RX", self.last_rx_value),
            ("TX Count", self.tx_count_value),
            ("RX Count", self.rx_count_value),
            ("Status Rows", self.status_count_value),
            ("Malformed Rows", self.malformed_value),
        ]

        for row, (name, value) in enumerate(labels):
            layout.addWidget(QLabel(name), row, 0)
            layout.addWidget(value, row, 1)

        return group

    def _build_console_group(self) -> QGroupBox:
        group = QGroupBox("Console")
        layout = QVBoxLayout(group)

        command_row = QWidget()
        command_layout = QHBoxLayout(command_row)
        command_layout.setContentsMargins(0, 0, 0, 0)
        command_layout.setSpacing(8)

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Manual command, for example: status or pid 1.2 0.02 0.08")
        self.command_input.returnPressed.connect(self.send_manual_command)

        send_button = QPushButton("Send")
        send_button.clicked.connect(self.send_manual_command)

        command_layout.addWidget(self.command_input, 1)
        command_layout.addWidget(send_button)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumBlockCount(800)

        self.trace_output = QPlainTextEdit()
        self.trace_output.setReadOnly(True)
        self.trace_output.setMaximumBlockCount(1500)
        self.trace_output.setPlaceholderText("Raw TX/RX trace appears here.")

        layout.addWidget(command_row)
        layout.addWidget(QLabel("Communication Trace"))
        layout.addWidget(self.trace_output, 1)
        layout.addWidget(QLabel("Application Log"))
        layout.addWidget(self.log_output, 1)
        return group

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #f5f0e8;
                color: #1d241f;
                font-family: "Avenir Next", "Helvetica Neue", sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #c6b59b;
                border-radius: 10px;
                margin-top: 12px;
                padding: 12px;
                background: #fcf8f2;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #5d4930;
            }
            QPushButton {
                background: #1b6b72;
                color: #f7f3eb;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #144d52;
            }
            QPushButton:disabled {
                background: #94aaa8;
            }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
                background: #fffdfa;
                border: 1px solid #ccbda7;
                border-radius: 8px;
                padding: 6px;
            }
            QPlainTextEdit {
                font-family: "SF Mono", "Menlo", monospace;
            }
            QLabel#titleLabel {
                font-size: 28px;
                font-weight: 700;
                color: #8f3e1d;
            }
            QLabel#subtitleLabel {
                color: #5d4930;
                margin-bottom: 6px;
            }
            """
        )

    def _make_gain_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1000.0, 1000.0)
        spin.setDecimals(4)
        spin.setSingleStep(0.05)
        return spin

    def _create_plot(self, title: str, x_label: str, y_label: str, curves: list[tuple[str, str]]) -> dict:
        widget = pg.PlotWidget()
        widget.setBackground("#fffdfa")
        widget.showGrid(x=True, y=True, alpha=0.18)
        widget.setTitle(title, color="#5d4930", size="14pt")
        widget.setLabel("bottom", x_label)
        widget.setLabel("left", y_label)
        widget.addLegend(offset=(12, 12))

        plot_curves = {}
        for name, color in curves:
            plot_curves[name] = widget.plot([], [], pen=pg.mkPen(color=color, width=2), name=name)

        return {"widget": widget, "curves": plot_curves}

    def refresh_ports(self) -> None:
        ports = list(list_ports.comports())
        current_port = self.port_combo.currentText()
        self.port_combo.clear()

        for port in ports:
            self.port_combo.addItem(port.device)

        if current_port:
            index = self.port_combo.findText(current_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

    def toggle_connection(self) -> None:
        if self.serial_port and self.serial_port.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self) -> None:
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "Serial Port", "Select a serial port first.")
            return

        try:
            self.serial_port = serial.Serial(port=port, baudrate=115200, timeout=0)
        except SerialException as exc:
            QMessageBox.critical(self, "Connection Failed", str(exc))
            self.serial_port = None
            return

        self.read_buffer.clear()
        self.reset_comm_counters()
        self.connection_value.setText("port open, waiting for firmware")
        self.port_state_value.setText(port)
        self.connect_button.setText("Disconnect")
        self.append_log(f"Connected to {port}")
        self.append_trace("SYS", f"opened serial port {port} @ 115200")
        self.request_status_update()

    def disconnect_serial(self) -> None:
        if self.serial_port:
            try:
                self.serial_port.close()
            except SerialException:
                pass

        self.serial_port = None
        self.connection_value.setText("disconnected")
        self.port_state_value.setText("closed")
        self.connect_button.setText("Connect")
        self.append_log("Disconnected")
        self.append_trace("SYS", "serial port closed")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.disconnect_serial()
        super().closeEvent(event)

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def append_trace(self, prefix: str, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.trace_output.appendPlainText(f"[{timestamp}] {prefix} {message}")

    def clear_trace(self) -> None:
        self.trace_output.clear()
        self.append_trace("SYS", "trace cleared")

    def reset_comm_counters(self) -> None:
        self.tx_count = 0
        self.rx_count = 0
        self.status_count = 0
        self.capture_row_count = 0
        self.malformed_count = 0
        self.last_tx_timestamp = "-"
        self.last_rx_timestamp = "-"
        self.update_comm_stats()

    def update_comm_stats(self) -> None:
        self.last_tx_value.setText(self.last_tx_timestamp)
        self.last_rx_value.setText(self.last_rx_timestamp)
        self.tx_count_value.setText(str(self.tx_count))
        self.rx_count_value.setText(str(self.rx_count))
        self.status_count_value.setText(str(self.status_count))
        self.malformed_value.setText(str(self.malformed_count))

    def send_command(self, command: str, *, quiet: bool = False) -> None:
        if not self.serial_port or not self.serial_port.is_open:
            if not quiet:
                self.append_log("Not connected.")
            return

        try:
            self.serial_port.write((command.strip() + "\n").encode("ascii"))
        except SerialException as exc:
            self.append_log(f"Write failed: {exc}")
            self.append_trace("ERR", f"write failed: {exc}")
            self.disconnect_serial()
            return

        self.tx_count += 1
        self.last_tx_timestamp = time.strftime("%H:%M:%S")
        self.update_comm_stats()

        if not quiet or self.trace_auto_checkbox.isChecked():
            self.append_trace("TX>", command.strip())

        if not quiet:
            self.append_log(f"> {command.strip()}")

    def send_manual_command(self) -> None:
        command = self.command_input.text().strip()
        if not command:
            return
        self.send_command(command)
        self.command_input.clear()

    def request_status_update(self) -> None:
        if not self.serial_port or not self.serial_port.is_open or self.capture_active:
            return
        self.send_command("statuscsv", quiet=True)

    def apply_pid(self) -> None:
        command = f"pid {self.kp_spin.value():.4f} {self.ki_spin.value():.4f} {self.kd_spin.value():.4f}"
        self.send_command(command)

    def arm_capture(self) -> None:
        command = (
            f"arm {self.capture_samples_spin.value()} "
            f"{self.capture_trigger_spin.value()} {self.capture_interval_spin.value()}"
        )
        self.send_command(command)

    def start_capture_now(self) -> None:
        command = f"capture {self.capture_samples_spin.value()} {self.capture_interval_spin.value()}"
        self.send_command(command)

    def poll_serial(self) -> None:
        if not self.serial_port or not self.serial_port.is_open:
            return

        try:
            waiting = self.serial_port.in_waiting
            if waiting <= 0:
                return

            self.read_buffer.extend(self.serial_port.read(waiting))
        except SerialException as exc:
            self.append_log(f"Read failed: {exc}")
            self.append_trace("ERR", f"read failed: {exc}")
            self.disconnect_serial()
            return

        while b"\n" in self.read_buffer:
            line, _, remainder = self.read_buffer.partition(b"\n")
            self.read_buffer = bytearray(remainder)
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded:
                self.process_line(decoded)

    def process_line(self, line: str) -> None:
        self.rx_count += 1
        self.last_rx_timestamp = time.strftime("%H:%M:%S")
        self.update_comm_stats()

        status = parse_status_line(line)
        if status is not None:
            if self.trace_auto_checkbox.isChecked():
                self.append_trace("RX<", line)
            self.handle_status(status)
            return

        if line == "# capture_begin":
            self.append_trace("RX<", line)
            self.capture_active = True
            self.capture_points = []
            self.capture_metadata = None
            self.capture_value.setText("capturing")
            self.append_log(line)
            return

        metadata = parse_capture_metadata(line)
        if metadata is not None:
            self.append_trace("RX<", line)
            self.capture_metadata = metadata
            self.append_log(
                f"Capture meta: kp={metadata.kp:.4f}, ki={metadata.ki:.4f}, kd={metadata.kd:.4f}, "
                f"samples={metadata.samples}, interval_ms={metadata.interval_ms}"
            )
            return

        if line == "# capture_end":
            self.append_trace("RX<", line)
            self.capture_active = False
            self.capture_value.setText("idle")
            self.append_log(line)
            self.update_capture_plot()
            return

        if line.startswith("sample,"):
            self.append_trace("RX<", line)
            return

        capture_point = parse_capture_point(line)
        if capture_point is not None:
            self.capture_row_count += 1
            if self.trace_auto_checkbox.isChecked():
                self.append_trace("RX<", line)
            self.capture_points.append(capture_point)
            if len(self.capture_points) % 5 == 0:
                self.update_capture_plot()
            return

        if line.startswith("status,") or line[:1].isdigit():
            self.malformed_count += 1
            self.update_comm_stats()
            self.append_trace("ERR", f"unparsed protocol row: {line}")
            self.append_log(f"Unparsed protocol row: {line}")
            return

        self.append_trace("RX<", line)
        self.append_log(line)

    def handle_status(self, status: LiveStatus) -> None:
        self.last_status = status
        self.status_count += 1

        time_seconds = status.timestamp_ms / 1000.0
        self.live_time.append(time_seconds)
        self.live_setpoint.append(status.setpoint)
        self.live_feedback.append(status.feedback)
        self.live_output.append(status.raw_output)
        self.live_pwm.append(status.pwm)

        self.controller_value.setText("enabled" if status.controller_enabled else "disabled")
        self.capture_value.setText(capture_state_name(status.capture_state))
        self.setpoint_value.setText(str(status.setpoint))
        self.feedback_value.setText(str(status.feedback))
        self.error_value.setText(str(status.error))
        self.output_value.setText(f"{status.raw_output:.2f}")
        self.pwm_value.setText(str(status.pwm))

        self._sync_spin_if_idle(self.kp_spin, status.kp)
        self._sync_spin_if_idle(self.ki_spin, status.ki)
        self._sync_spin_if_idle(self.kd_spin, status.kd)
        self._sync_spin_if_idle(self.capture_samples_spin, status.capture_samples)
        self._sync_spin_if_idle(self.capture_trigger_spin, status.capture_trigger_delta)
        self._sync_spin_if_idle(self.capture_interval_spin, status.capture_interval_ms)

        self.connection_value.setText("firmware responding")
        self.update_comm_stats()
        self.update_live_plots()

    def _sync_spin_if_idle(self, widget, value) -> None:
        if widget.hasFocus():
            return
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)

    def update_live_plots(self) -> None:
        if not self.live_time:
            return

        start_time = self.live_time[0]
        x_values = [value - start_time for value in self.live_time]

        self.live_plot["curves"]["Setpoint"].setData(x_values, list(self.live_setpoint))
        self.live_plot["curves"]["Feedback"].setData(x_values, list(self.live_feedback))
        self.live_drive_plot["curves"]["Raw Output"].setData(x_values, list(self.live_output))
        self.live_drive_plot["curves"]["PWM"].setData(x_values, list(self.live_pwm))

    def update_capture_plot(self) -> None:
        if not self.capture_points:
            self.capture_plot["curves"]["Setpoint"].setData([], [])
            self.capture_plot["curves"]["Feedback"].setData([], [])
            return

        start_time = self.capture_points[0].timestamp_ms / 1000.0
        x_values = [(point.timestamp_ms / 1000.0) - start_time for point in self.capture_points]
        setpoints = [point.setpoint for point in self.capture_points]
        feedback = [point.feedback for point in self.capture_points]

        self.capture_plot["curves"]["Setpoint"].setData(x_values, setpoints)
        self.capture_plot["curves"]["Feedback"].setData(x_values, feedback)

    def save_capture_csv(self) -> None:
        if not self.capture_points:
            QMessageBox.information(self, "Save Capture", "No capture data is available yet.")
            return

        default_path = Path.cwd() / "capture.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Capture CSV",
            str(default_path),
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        with open(file_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if self.capture_metadata is not None:
                writer.writerow(
                    [
                        "#",
                        f"kp={self.capture_metadata.kp}",
                        f"ki={self.capture_metadata.ki}",
                        f"kd={self.capture_metadata.kd}",
                        f"samples={self.capture_metadata.samples}",
                        f"interval_ms={self.capture_metadata.interval_ms}",
                        f"trigger_delta={self.capture_metadata.trigger_delta}",
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
            for point in self.capture_points:
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

        self.append_log(f"Saved capture to {file_path}")
