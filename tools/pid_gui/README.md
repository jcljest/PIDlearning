# PID GUI

Host-side desktop GUI for the `PIDtest` sketch.

## What it does

- Connects to the board over serial
- Polls compact `statuscsv` telemetry for live plots
- Lets you change `Kp`, `Ki`, and `Kd` without reflashing
- Arms triggered captures or starts immediate captures
- Plots captured oscillation data and exports it to CSV

## Firmware requirement

This GUI expects the sketch in this repo with the `statuscsv` command enabled.

## Setup

```bash
cd /Users/laij/Documents/PlatformIO/Projects/PIDtest/tools/pid_gui
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

## Typical workflow

1. Flash the board and open the GUI.
2. Select the serial port and connect.
3. Adjust `Kp`, `Ki`, and `Kd`, then click `Apply Gains`.
4. Click `Arm Triggered Capture` and move the setpoint pot to trigger a run.
5. Inspect the capture plot and save the CSV if needed.

## Serial commands used by the GUI

- `statuscsv`
- `pid <kp> <ki> <kd>`
- `run`
- `stop`
- `reset`
- `arm <samples> <trigger_delta> <interval_ms>`
- `capture <samples> <interval_ms>`
- `cancel`
