# Driver drowsiness detection

Watches the driver through an IR camera and raises escalating alerts when
drowsiness is detected. Speed from an OBD-II adapter is optional. When the
vehicle is stopped, the assistant does not give the pull-over prompt.

## Project layout

```
main.py              entry point: camera loop, wiring
config.py            all thresholds and timings
detection/
  landmarks.py       MediaPipe face mesh wrapper
  metrics.py         EAR (eyes), MAR (mouth). Pure NumPy, unit-tested
  state.py           PERCLOS window, drowsy episodes, yawn counting, alert level
alerts/
  escalation.py      when to fire and how often to repeat
  audio.py           bell, console message, optional speech
vehicle/
  obd.py             OBD-II speed (optional)
telemetry/
  logger.py          per-frame CSV for tuning
tests/               run with pytest, no camera needed
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-device.txt
```

## Run

```bash
python main.py                                  # video window and speech
python main.py --no-voice --no-display          # headless, bell and console only
python main.py --obd-port /dev/rfcomm0 --log drive.csv
```

Press `q` in the video window to quit.

## Test

```bash
pytest
```

The tests cover the metric formulas, the state machine (timing, PERCLOS,
yawns, speed cap, face loss), and alert repeat timing. They do not need a camera.

## Tuning

Start with the defaults in `config.py`. Then run a few drives with `--log`
and check the CSV:

- **Too many false alarms:** raise `ear_threshold` slightly, or raise `eye_closed_onset_s`.
  Look at EAR during normal blinks. A blink should stay below `eye_closed_onset_s`.
- **Misses real drowsiness:** lower `ear_threshold`, or lower `perclos_threshold`.
  Check `perclos` in the log during the event.
- **Camera distance or glasses:** EAR depends on face size and lighting. Check the
  open-eye EAR value for each driver and set the threshold below it.

## Limits and safety

- This is a driver aid, not a safety system. It cannot brake or steer the vehicle.
  Stopping a car safely needs the manufacturer's own driver-monitoring integration.
- Detection depends on a clear view of the face. Sunglasses, a hand over the face,
  or the camera being blocked can cause misses. The overlay shows "no face detected".
- Do not test on public roads without a second person in the car, and never test
  while driving alone.
