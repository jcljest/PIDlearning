import sys
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import serial
import serial.tools.list_ports


BAUD = 115200
POLL_INTERVAL = 0.02
MAX_POINTS = 10000
FOLLOW_WINDOW_SECONDS = 10.0

# Set to None for auto-detect, or hardcode a port like:
# PORT = "/dev/cu.usbmodem1101"
PORT = "/dev/cu.usbmodem101"

# Tuning increments
KP_STEP = 0.050
KI_STEP = 0.010
KD_STEP = 0.001


class TelemetryViewer:
    def __init__(self, port: str, baud: int):
        self.ser = serial.Serial(port, baud, timeout=0.05)
        time.sleep(2.0)  # many boards reset on serial open

        self.buffer = ""
        self.last_poll_time = 0.0
        self.start_ms = None

        self.t = deque(maxlen=MAX_POINTS)
        self.setpoint = deque(maxlen=MAX_POINTS)
        self.feedback = deque(maxlen=MAX_POINTS)
        self.error = deque(maxlen=MAX_POINTS)
        self.pwm = deque(maxlen=MAX_POINTS)
        self.p_term = deque(maxlen=MAX_POINTS)
        self.i_term = deque(maxlen=MAX_POINTS)
        self.d_term = deque(maxlen=MAX_POINTS)

        # Last-known gains from telemetry
        self.kp = None
        self.ki = None
        self.kd = None

    def send_command(self, text: str) -> None:
        cmd = text.strip() + "\n"
        self.ser.write(cmd.encode("utf-8"))
        print(f">>> {text}")

    def send_status_request(self) -> None:
        self.send_command("statuscsv")

    def read_lines(self):
        waiting = self.ser.in_waiting
        if waiting:
            data = self.ser.read(waiting).decode("utf-8", errors="replace")
            self.buffer += data

        lines = []
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.strip()
            if line:
                lines.append(line)
        return lines

    def parse_status_line(self, line: str):
        parts = line.split(",")

        # Expected format:
        # status,timestamp,setpoint,feedback,error,p,i,d,output,pwm,direction,
        # deadband,saturated,kp,ki,kd,controller_enabled,capture_state,
        # capture_samples,capture_trigger_delta,capture_interval_ms
        if len(parts) != 21 or parts[0] != "status":
            return None

        try:
            return {
                "timestamp_ms": int(parts[1]),
                "setpoint": int(parts[2]),
                "feedback": int(parts[3]),
                "error": int(parts[4]),
                "p_term": float(parts[5]),
                "i_term": float(parts[6]),
                "d_term": float(parts[7]),
                "pwm": int(parts[9]),
                "kp": float(parts[13]),
                "ki": float(parts[14]),
                "kd": float(parts[15]),
            }
        except ValueError:
            return None

    def update_data(self) -> None:
        now = time.time()
        if now - self.last_poll_time >= POLL_INTERVAL:
            self.send_status_request()
            self.last_poll_time = now

        for line in self.read_lines():
            parsed = self.parse_status_line(line)
            if parsed is None:
                # Show non-status lines so help/status responses remain visible
                if not line.startswith("status,"):
                    print(line)
                continue

            if self.start_ms is None:
                self.start_ms = parsed["timestamp_ms"]

            elapsed_s = (parsed["timestamp_ms"] - self.start_ms) / 1000.0

            self.t.append(elapsed_s)
            self.setpoint.append(parsed["setpoint"])
            self.feedback.append(parsed["feedback"])
            self.error.append(parsed["error"])
            self.pwm.append(parsed["pwm"])
            self.p_term.append(parsed["p_term"])
            self.i_term.append(parsed["i_term"])
            self.d_term.append(parsed["d_term"])

            self.kp = parsed["kp"]
            self.ki = parsed["ki"]
            self.kd = parsed["kd"]

    def close(self) -> None:
        if self.ser.is_open:
            self.ser.close()


def auto_detect_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        raise RuntimeError("No serial ports found.")

    preferred = []
    for p in ports:
        dev = p.device
        desc = (p.description or "").lower()
        if "bluetooth" in dev.lower() or "bluetooth" in desc:
            continue
        if "usbmodem" in dev.lower() or "usbserial" in dev.lower():
            preferred.append(dev)

    if preferred:
        return preferred[0]

    for p in ports:
        dev = p.device
        if "bluetooth" not in dev.lower():
            return dev

    raise RuntimeError("Could not find a suitable serial port.")


def main():
    port = PORT
    if len(sys.argv) > 1:
        port = sys.argv[1]
    elif port is None:
        port = auto_detect_port()

    print(f"Opening serial port: {port}")
    print()
    print("Controls")
    print("--------")
    print("f  : toggle follow-live mode")
    print("r  : return to live window")
    print("q  : quit")
    print("g  : send run")
    print("x  : send stop")
    print("z  : send reset")
    print("h  : send help")
    print("s  : send status")
    print("u/j: kp up/down")
    print("i/k: ki up/down")
    print("o/l: kd up/down")
    print()

    viewer = TelemetryViewer(port, BAUD)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 8), sharex=True)

    line_setpoint, = ax1.plot([], [], label="Setpoint")
    line_feedback, = ax1.plot([], [], label="Feedback")

    line_error, = ax2.plot([], [], label="Error")
    line_pwm, = ax2.plot([], [], label="PWM")

    line_p, = ax3.plot([], [], label="P term")
    line_i, = ax3.plot([], [], label="I term")
    line_d, = ax3.plot([], [], label="D term")

    ax1.set_ylabel("ADC")
    ax2.set_ylabel("Error / PWM")
    ax3.set_ylabel("PID terms")
    ax3.set_xlabel("Time (s)")

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper left")
    ax3.legend(loc="upper left")

    ax1.grid(True)
    ax2.grid(True)
    ax3.grid(True)

    follow_live = True

    info_text = fig.text(
        0.01,
        0.99,
        "KP=--  KI=--  KD=--  follow_live=True",
        va="top",
        ha="left",
    )

    def autoscale_axis(axis, y_values, pad=1.0):
        if not y_values:
            return
        ymin = min(y_values)
        ymax = max(y_values)
        if ymin == ymax:
            ymin -= pad
            ymax += pad
        else:
            span = ymax - ymin
            ymin -= 0.08 * span
            ymax += 0.08 * span
        axis.set_ylim(ymin, ymax)

    def send_gain(name: str, value: float):
        viewer.send_command(f"{name} {value:.4f}")

    def on_key(event):
        nonlocal follow_live

        key = event.key.lower() if event.key else ""

        if key == "f":
            follow_live = not follow_live
            print(f"follow_live = {follow_live}")

        elif key == "r" and viewer.t:
            follow_live = True
            latest = viewer.t[-1]
            xmin = max(0.0, latest - FOLLOW_WINDOW_SECONDS)
            ax1.set_xlim(xmin, latest)
            ax2.set_xlim(xmin, latest)
            ax3.set_xlim(xmin, latest)
            fig.canvas.draw_idle()
            print("Returned to live window.")

        elif key == "q":
            plt.close(fig)

        elif key == "g":
            viewer.send_command("run")

        elif key == "x":
            viewer.send_command("stop")

        elif key == "z":
            viewer.send_command("reset")

        elif key == "h":
            viewer.send_command("help")

        elif key == "s":
            viewer.send_command("status")

        elif key == "u":
            if viewer.kp is not None:
                viewer.kp += KP_STEP
                send_gain("kp", viewer.kp)

        elif key == "j":
            if viewer.kp is not None:
                viewer.kp -= KP_STEP
                send_gain("kp", viewer.kp)

        elif key == "i":
            if viewer.ki is not None:
                viewer.ki += KI_STEP
                send_gain("ki", viewer.ki)

        elif key == "k":
            if viewer.ki is not None:
                viewer.ki -= KI_STEP
                send_gain("ki", viewer.ki)

        elif key == "o":
            if viewer.kd is not None:
                viewer.kd += KD_STEP
                send_gain("kd", viewer.kd)

        elif key == "l":
            if viewer.kd is not None:
                viewer.kd -= KD_STEP
                send_gain("kd", viewer.kd)

    fig.canvas.mpl_connect("key_press_event", on_key)

    def animate(_frame):
        viewer.update_data()

        kp_str = f"{viewer.kp:.4f}" if viewer.kp is not None else "--"
        ki_str = f"{viewer.ki:.4f}" if viewer.ki is not None else "--"
        kd_str = f"{viewer.kd:.4f}" if viewer.kd is not None else "--"
        info_text.set_text(
            f"KP={kp_str}  KI={ki_str}  KD={kd_str}  follow_live={follow_live}"
        )

        if not viewer.t:
            return (
                line_setpoint, line_feedback,
                line_error, line_pwm,
                line_p, line_i, line_d,
                info_text,
            )

        x = list(viewer.t)

        line_setpoint.set_data(x, list(viewer.setpoint))
        line_feedback.set_data(x, list(viewer.feedback))
        line_error.set_data(x, list(viewer.error))
        line_pwm.set_data(x, list(viewer.pwm))
        line_p.set_data(x, list(viewer.p_term))
        line_i.set_data(x, list(viewer.i_term))
        line_d.set_data(x, list(viewer.d_term))

        if follow_live:
            latest = x[-1]
            xmin = max(0.0, latest - FOLLOW_WINDOW_SECONDS)
            ax1.set_xlim(xmin, latest)
            ax2.set_xlim(xmin, latest)
            ax3.set_xlim(xmin, latest)

            autoscale_axis(ax1, list(viewer.setpoint) + list(viewer.feedback), pad=10.0)
            autoscale_axis(ax2, list(viewer.error) + list(viewer.pwm), pad=10.0)
            autoscale_axis(ax3, list(viewer.p_term) + list(viewer.i_term) + list(viewer.d_term), pad=1.0)

        return (
            line_setpoint, line_feedback,
            line_error, line_pwm,
            line_p, line_i, line_d,
            info_text,
        )

    ani = FuncAnimation(fig, animate, interval=50, blit=False, cache_frame_data=False)

    try:
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()
    finally:
        viewer.close()


if __name__ == "__main__":
    main()