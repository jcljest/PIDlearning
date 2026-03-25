from __future__ import annotations

import time
from pathlib import Path

from serial import SerialException
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
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from capture_controller import CaptureController
from csv_export import export_session_csv
from plot_adapter import PlotBundle, clear_plot, create_plot, set_plot_data
from protocol import parse_capture_metadata, parse_capture_point, parse_status_line
from serial_client import SerialClient, available_ports
from session_state import SessionState


class PidTuningWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PID Capture Console")
        self.resize(1460, 920)

        self.serial_client = SerialClient()
        self.state = SessionState()
        self.capture_controller = CaptureController(self.state)

        self._build_ui()
        self._apply_style()
        self.refresh_ports()
        self.refresh_state_widgets()

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

        title = QLabel("PID Live Tuning Console")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Connect, apply gains, start a triggered run, and keep the serial trace visible.")
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
        control_layout.addWidget(self._build_session_group())
        control_layout.addWidget(self._build_status_group())
        control_layout.addWidget(self._build_console_group(), 1)

        control_scroll = QScrollArea()
        control_scroll.setWidgetResizable(True)
        control_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        control_scroll.setWidget(control_panel)

        plots_panel = QWidget()
        plots_layout = QVBoxLayout(plots_panel)
        plots_layout.setContentsMargins(0, 0, 0, 0)
        plots_layout.setSpacing(12)

        self.live_plot = create_plot(
            "Live Position",
            "Time (s)",
            "Counts",
            [("Setpoint", "#db6a32"), ("Feedback", "#1b6b72")],
        )
        self.live_drive_plot = create_plot(
            "Live Drive",
            "Time (s)",
            "Drive",
            [("Raw Output", "#5b4db2"), ("PWM", "#a23a72")],
        )
        self.snapshot_plot = create_plot(
            "Run Snapshot",
            "Time (s)",
            "Counts",
            [("Setpoint", "#db6a32"), ("Feedback", "#1b6b72")],
        )

        plots_layout.addWidget(self.live_plot.widget, 1)
        plots_layout.addWidget(self.live_drive_plot.widget, 1)
        plots_layout.addWidget(self.snapshot_plot.widget, 1)

        splitter.addWidget(control_scroll)
        splitter.addWidget(plots_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 1040])

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("1. Connection")
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
        group = QGroupBox("2. PID")
        layout = QFormLayout(group)

        helper = QLabel(
            "Change the gains here, then click Apply Gains. The latest values from the board sync back into these fields."
        )
        helper.setWordWrap(True)

        self.kp_spin = self._make_gain_spin()
        self.ki_spin = self._make_gain_spin()
        self.kd_spin = self._make_gain_spin()
        self.apply_pid_button = QPushButton("Apply Gains")
        self.apply_pid_button.clicked.connect(self.apply_pid)

        layout.addRow(helper)
        layout.addRow("Kp", self.kp_spin)
        layout.addRow("Ki", self.ki_spin)
        layout.addRow("Kd", self.kd_spin)
        layout.addRow(self.apply_pid_button)
        return group

    def _build_session_group(self) -> QGroupBox:
        group = QGroupBox("3. Run Session")
        layout = QFormLayout(group)

        helper = QLabel(
            "Start Triggered Run enables the controller and waits until the setpoint changes by Trigger Delta. "
            "Stop Run freezes the live plots and time."
        )
        helper.setWordWrap(True)

        self.capture_trigger_spin = QSpinBox()
        self.capture_trigger_spin.setRange(1, 1023)
        self.capture_trigger_spin.setValue(25)

        self.run_session_button = QPushButton("Start Triggered Run")
        self.save_button = QPushButton("Save Data CSV")
        self.run_session_button.clicked.connect(self.toggle_run_session)
        self.save_button.clicked.connect(self.save_run_csv)

        layout.addRow(helper)
        layout.addRow("Trigger Delta", self.capture_trigger_spin)
        layout.addRow(self.run_session_button)
        layout.addRow(self.save_button)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("4. Status")
        layout = QGridLayout(group)

        self.connection_value = QLabel("disconnected")
        self.port_state_value = QLabel("closed")
        self.controller_value = QLabel("unknown")
        self.live_capture_value = QLabel("idle")
        self.live_duration_value = QLabel("0.00 s")
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
            ("Run State", self.live_capture_value),
            ("Run Time", self.live_duration_value),
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
        group = QGroupBox("5. Diagnostics")
        layout = QVBoxLayout(group)

        helper = QLabel(
            "The trace shows raw serial traffic. Use the command box only for advanced debugging if the main workflow is not enough."
        )
        helper.setWordWrap(True)

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

        layout.addWidget(helper)
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
            QLabel {
                background: transparent;
            }
            """
        )

    def _make_gain_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-1000.0, 1000.0)
        spin.setDecimals(4)
        spin.setSingleStep(0.05)
        return spin

    def _timestamp(self) -> str:
        return time.strftime("%H:%M:%S")

    def refresh_ports(self) -> None:
        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        for port in available_ports():
            self.port_combo.addItem(port)

        if current_port:
            index = self.port_combo.findText(current_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

    def toggle_connection(self) -> None:
        if self.serial_client.is_open:
            self.disconnect_serial()
        else:
            self.connect_serial()

    def connect_serial(self) -> None:
        port = self.port_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "Serial Port", "Select a serial port first.")
            return

        try:
            self.serial_client.connect(port, baudrate=115200)
        except SerialException as exc:
            QMessageBox.critical(self, "Connection Failed", str(exc))
            return

        self.state = SessionState()
        self.capture_controller = CaptureController(self.state)

        self.append_log(f"Connected to {port}")
        self.append_trace("SYS", f"opened serial port {port} @ 115200")
        self.refresh_state_widgets()
        self.request_status_update()

    def disconnect_serial(self) -> None:
        self.serial_client.disconnect()
        self.capture_controller.reset()
        self.refresh_state_widgets()
        self.append_log("Disconnected")
        self.append_trace("SYS", "serial port closed")

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.disconnect_serial()
        super().closeEvent(event)

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def append_trace(self, prefix: str, message: str) -> None:
        self.trace_output.appendPlainText(f"[{self._timestamp()}] {prefix} {message}")

    def clear_trace(self) -> None:
        self.trace_output.clear()
        self.append_trace("SYS", "trace cleared")

    def refresh_state_widgets(self) -> None:
        self.connection_value.setText("firmware responding" if self.state.last_status else ("port open, waiting for firmware" if self.serial_client.is_open else "disconnected"))
        self.port_state_value.setText(self.serial_client.port_name)
        self.controller_value.setText(
            "enabled" if self.state.last_status and self.state.last_status.controller_enabled else ("unknown" if self.state.last_status is None else "disabled")
        )
        self.live_capture_value.setText(self.capture_controller.live_state_label)
        self.live_duration_value.setText(f"{self.state.live_capture_duration_ms / 1000.0:.2f} s")
        self.setpoint_value.setText(str(self.state.last_status.setpoint) if self.state.last_status else "-")
        self.feedback_value.setText(str(self.state.last_status.feedback) if self.state.last_status else "-")
        self.error_value.setText(str(self.state.last_status.error) if self.state.last_status else "-")
        self.output_value.setText(f"{self.state.last_status.raw_output:.2f}" if self.state.last_status else "-")
        self.pwm_value.setText(str(self.state.last_status.pwm) if self.state.last_status else "-")
        self.last_tx_value.setText(self.state.last_tx_timestamp)
        self.last_rx_value.setText(self.state.last_rx_timestamp)
        self.tx_count_value.setText(str(self.state.tx_count))
        self.rx_count_value.setText(str(self.state.rx_count))
        self.status_count_value.setText(str(self.state.status_count))
        self.malformed_value.setText(str(self.state.malformed_count))
        self.run_session_button.setText(self.capture_controller.run_button_text)
        self.connect_button.setText("Disconnect" if self.serial_client.is_open else "Connect")

    def send_command(self, command: str, *, quiet: bool = False) -> None:
        if not self.serial_client.is_open:
            if not quiet:
                self.append_log("Not connected.")
            return

        try:
            self.serial_client.send_line(command)
        except (RuntimeError, SerialException) as exc:
            self.append_log(f"Write failed: {exc}")
            self.append_trace("ERR", f"write failed: {exc}")
            self.disconnect_serial()
            return

        self.state.record_tx(self._timestamp())
        self.refresh_state_widgets()

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
        if not self.serial_client.is_open or self.state.capture_active:
            return
        self.send_command("statuscsv", quiet=True)

    def apply_pid(self) -> None:
        command = f"pid {self.kp_spin.value():.4f} {self.ki_spin.value():.4f} {self.kd_spin.value():.4f}"
        self.send_command(command)

    def toggle_run_session(self) -> None:
        if self.state.live_mode in {"armed", "recording"}:
            self.stop_controller()
            return

        self.send_command("run")
        messages = self.capture_controller.arm(
            baseline_setpoint=self.state.last_status.setpoint if self.state.last_status else None,
            trigger_delta=self.capture_trigger_spin.value(),
        )
        for message in messages:
            self.append_log(message)
        self.refresh_state_widgets()
        self.update_live_plots()
        self.update_snapshot_plot()

    def stop_controller(self) -> None:
        for message in self.capture_controller.stop("Live run stopped by user."):
            self.append_log(message)
        self.send_command("stop")
        self.refresh_state_widgets()

    def poll_serial(self) -> None:
        if not self.serial_client.is_open:
            return

        try:
            lines = self.serial_client.read_available_lines()
        except SerialException as exc:
            self.append_log(f"Read failed: {exc}")
            self.append_trace("ERR", f"read failed: {exc}")
            self.disconnect_serial()
            return

        for line in lines:
            self.process_line(line)

    def process_line(self, line: str) -> None:
        self.state.record_rx(self._timestamp())
        self.refresh_state_widgets()

        status = parse_status_line(line)
        if status is not None:
            if self.trace_auto_checkbox.isChecked():
                self.append_trace("RX<", line)
            self.handle_status(status)
            return

        if line == "# capture_begin":
            self.state.capture_active = True
            self.state.capture_points.clear()
            self.state.capture_metadata = None
            self.append_trace("RX<", line)
            self.append_log(line)
            self.refresh_state_widgets()
            return

        metadata = parse_capture_metadata(line)
        if metadata is not None:
            self.state.capture_metadata = metadata
            self.append_trace("RX<", line)
            self.append_log(
                f"Capture meta: kp={metadata.kp:.4f}, ki={metadata.ki:.4f}, kd={metadata.kd:.4f}, "
                f"samples={metadata.samples}, interval_ms={metadata.interval_ms}"
            )
            return

        if line == "# capture_end":
            self.state.capture_active = False
            self.append_trace("RX<", line)
            self.append_log(line)
            self.update_snapshot_plot()
            self.refresh_state_widgets()
            return

        if line.startswith("sample,"):
            self.append_trace("RX<", line)
            return

        capture_point = parse_capture_point(line)
        if capture_point is not None:
            self.state.record_capture_row()
            self.state.capture_points.append(capture_point)
            if self.trace_auto_checkbox.isChecked():
                self.append_trace("RX<", line)
            if len(self.state.capture_points) % 5 == 0:
                self.update_snapshot_plot()
            self.refresh_state_widgets()
            return

        if line.startswith("status,") or line[:1].isdigit():
            self.state.record_malformed()
            self.append_trace("ERR", f"unparsed protocol row: {line}")
            self.append_log(f"Unparsed protocol row: {line}")
            self.refresh_state_widgets()
            return

        self.append_trace("RX<", line)
        self.append_log(line)

    def handle_status(self, status) -> None:
        self.state.last_status = status
        self.state.record_status()
        self._sync_spin_if_idle(self.kp_spin, status.kp)
        self._sync_spin_if_idle(self.ki_spin, status.ki)
        self._sync_spin_if_idle(self.kd_spin, status.kd)
        self._sync_spin_if_idle(self.capture_trigger_spin, status.capture_trigger_delta)

        messages = self.capture_controller.consume_status(status, self.capture_trigger_spin.value())
        for message in messages:
            self.append_log(message)

        self.refresh_state_widgets()
        self.update_live_plots()
        self.update_snapshot_plot()

    def _sync_spin_if_idle(self, widget, value) -> None:
        if widget.hasFocus():
            return
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)

    def update_live_plots(self) -> None:
        if not self.state.live_run_rows:
            clear_plot(self.live_plot)
            clear_plot(self.live_drive_plot)
            return

        x_values = [row.elapsed_ms / 1000.0 for row in self.state.live_run_rows]
        set_plot_data(
            self.live_plot,
            x_values,
            {
                "Setpoint": [row.status.setpoint for row in self.state.live_run_rows],
                "Feedback": [row.status.feedback for row in self.state.live_run_rows],
            },
        )
        set_plot_data(
            self.live_drive_plot,
            x_values,
            {
                "Raw Output": [row.status.raw_output for row in self.state.live_run_rows],
                "PWM": [row.status.pwm for row in self.state.live_run_rows],
            },
        )

    def update_snapshot_plot(self) -> None:
        if self.state.live_run_rows:
            x_values = [row.elapsed_ms / 1000.0 for row in self.state.live_run_rows]
            set_plot_data(
                self.snapshot_plot,
                x_values,
                {
                    "Setpoint": [row.status.setpoint for row in self.state.live_run_rows],
                    "Feedback": [row.status.feedback for row in self.state.live_run_rows],
                },
            )
            return

        if not self.state.capture_points:
            clear_plot(self.snapshot_plot)
            return

        x_values = [
            (point.timestamp_ms - self.state.capture_points[0].timestamp_ms) / 1000.0
            for point in self.state.capture_points
        ]
        set_plot_data(
            self.snapshot_plot,
            x_values,
            {
                "Setpoint": [point.setpoint for point in self.state.capture_points],
                "Feedback": [point.feedback for point in self.state.capture_points],
            },
        )

    def save_run_csv(self) -> None:
        if not self.state.live_run_rows and not self.state.capture_points:
            QMessageBox.information(self, "Save Data", "No run data is available yet.")
            return

        default_path = Path.cwd() / "live_run.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Data CSV",
            str(default_path),
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        try:
            export_session_csv(
                file_path=file_path,
                live_run_rows=self.state.live_run_rows,
                capture_points=self.state.capture_points,
                capture_metadata=self.state.capture_metadata,
            )
        except ValueError as exc:
            QMessageBox.information(self, "Save Data", str(exc))
            return

        self.append_log(f"Saved data to {file_path}")
