# PID GUI

Host-side desktop GUI for the `PIDtest` sketch.

## What it does

- Connects to the board over serial
- Polls compact `statuscsv` telemetry for live plots
- Lets you change `Kp`, `Ki`, and `Kd` without reflashing
- Starts a triggered live run from the GUI
- Keeps a raw serial trace visible for debugging
- Exports either the live run or firmware capture data to CSV

## Module layout

```text
tools/pid_gui/
├── app.py
├── main_window.py
├── protocol.py
├── serial_client.py
├── session_state.py
├── capture_controller.py
├── plot_adapter.py
├── csv_export.py
└── tests/
    ├── test_protocol.py
    ├── test_capture_controller.py
    └── test_csv_export.py
```

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
4. Click `Start Triggered Run` and move the setpoint pot to trigger a run.
5. Inspect the capture plot and save the CSV if needed.

## Tests

```bash
cd /Users/laij/Documents/PlatformIO/Projects/PIDtest
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m unittest discover tools/pid_gui/tests
```

## Serial commands used by the GUI

- `statuscsv`
- `pid <kp> <ki> <kd>`
- `run`
- `stop`
- `reset`
- `arm <samples> <trigger_delta> <interval_ms>`
- `capture <samples> <interval_ms>`
- `cancel`
