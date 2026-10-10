# Driver Drowsiness Detection: Project Report

## 1. Purpose

The project is a driver-monitoring assistant. A camera watches the driver's face and detects signs of drowsiness, such as long eye closures, frequent yawning, and high PERCLOS (the share of time the eyes are closed). It then raises alerts that escalate in severity. It can be installed in a vehicle, and it can use the vehicle's speed from an OBD-II adapter.

It is a driver aid. It cannot brake or steer the vehicle. The "pull over" prompt is spoken or displayed, and it is suppressed when the vehicle is stopped.

## 2. How it works

The data flows through these stages in order:

```
IR camera → face landmarks → eye and mouth metrics → drowsiness state machine
          → alert controller → alert outputs (bell, speech, GPIO buzzer)
                                    ↘ CSV telemetry log
OBD-II speed (optional) ────────────→ state machine
```

1. **Capture:** OpenCV reads frames from the camera at 640×480.
2. **Landmarks:** MediaPipe Face Mesh finds 478 face points per frame, including iris points.
3. **Metrics:**
   - **EAR (Eye Aspect Ratio):** the eyelid opening relative to eye width. Open eyes are about 0.3, and closed eyes drop toward 0.
   - **MAR (Mouth Aspect Ratio):** mouth opening relative to mouth width. Large values indicate a yawn.
4. **State machine:**
   - A drowsy episode starts when the eyes stay closed for 1.5 seconds, or when PERCLOS reaches 35% over 60 seconds.
   - An episode ends after 10 consecutive frames with open eyes.
   - Yawns count only if the mouth stays open for at least 1 second. Three yawns within 5 minutes raise a warning.
   - Severity rises with episode length: warning at the start, alert after 4 seconds, critical after 8 seconds.
   - Critical is capped at alert when the vehicle is moving below 10 km/h.
5. **Alerts:**
   - Each level has its own pattern: warning sounds one short beep, alert sounds two, and critical sounds three.
   - Escalation fires immediately. Repeats follow a fixed interval for each level.
   - Output goes to the terminal bell and console, optional speech, and an optional GPIO buzzer. A failing output does not stop the others.
6. **Logging:** each frame writes a CSV row with EAR, MAR, PERCLOS, speed, level, and reason, so thresholds can be tuned from real drives.

## 3. What it was built with

| Area | Tools |
|---|---|
| Language | Python 3.10–3.11 recommended |
| Computer vision | OpenCV (camera and drawing), MediaPipe 0.10.14 (face landmarks; pinned because the `solutions` API is used) |
| Numerics | NumPy |
| Speech (optional) | pyttsx3 |
| Vehicle data (optional) | python-obd, with an ELM327 OBD-II adapter |
| Raspberry Pi GPIO | gpiozero, lgpio |
| Testing | pytest (the target runner; see section 5) |
| Deployment | systemd service, logrotate, a bash install script |
| Version control | Git, hosted on GitHub |

**Hardware:** a Raspberry Pi 4 or 5 (or a laptop for development), an IR camera such as the Pi NoIR module, a buzzer on GPIO 17, a speaker, and an ELM327 OBD-II adapter.

## 4. How it was developed

The project was built in layers, and each layer was checked before the next was added:

1. **Pure logic first.** EAR and MAR are plain NumPy functions with no camera dependency, so they could be tested with synthetic coordinates.
2. **State machine with injected timestamps.** The monitor takes the time as an argument instead of reading the clock. This made timing behavior testable.
3. **Hardware behind thin wrappers.** MediaPipe, OBD-II, and GPIO are imported only when used. The unit tests and `--help` run without them.
4. **Alert logic separated from output.** The escalation controller depends on a notifier interface, so it can be tested with a fake notifier.
5. **Operational pieces last.** CSV logging, the GPIO buzzer, the systemd service, and the install script were added after the core worked.

The project layout:

```
main.py                 entry point, camera loop, argument parsing
config.py               all thresholds and timings
detection/              landmarks, metrics, state machine
alerts/                 escalation, speech and bell, GPIO buzzer
vehicle/obd.py          OBD-II speed
telemetry/logger.py     CSV logging
tests/                  20 unit tests
deploy/                 systemd unit, logrotate config, install.sh
docs/REPORT.md          this report
README.md, requirements*.txt, .gitignore
```

The package named `logging` was renamed to `telemetry` so it would not shadow Python's standard `logging` module.

## 5. Verification status

**Verified:**
- All 20 unit tests pass. They cover EAR and MAR formulas, the timing of drowsy episodes, PERCLOS, yawn counting, the speed cap, face-loss handling, alert escalation and repeat timing, buzzer patterns, cancellation, and output failure isolation.
- All modules compile, and the command-line help works.
- The app exits cleanly when no camera is present.

**Not verified:**
- **pytest** was not available in the build environment, so the tests were run with a small local runner that calls each test function. Running `pytest` on your machine should give the same result.
- **Camera and MediaPipe pipeline:** there is no webcam in the build environment, so face detection and the EAR and MAR values from real faces have never been measured.
- **Thresholds:** the default values are reasonable starting points from the literature, not tuned values for any real camera or driver.
- **Raspberry Pi installation, the GPIO buzzer, and the systemd service** have not been run on hardware.

## 6. Known limitations

- **PERCLOS counts frames, not time.** It assumes a steady frame rate. A slow or dropped frame rate would skew it.
- **A blink during fatigue restarts the episode.** The escalation timer resets, which can delay the critical alert. A more robust approach would track the total drowsy time within a window.
- **No head-pose detection.** Nodding or head drooping is not implemented.
- **Face detection depends on the view.** Sunglasses, a hand over the face, or an obstructed camera cause missed detections. The overlay shows "no face detected" in that case.
- **Lighting and glasses** can change EAR, so each driver may need their own threshold.
- **Not a certified safety system.** It cannot stop the vehicle, and it is not a substitute for manufacturer driver-monitoring systems.

## 7. Next steps

1. Run the app on a laptop with a webcam and record a drive log with `--log drive.csv`.
2. Tune `config.py` from that log, especially `ear_threshold` and `perclos_threshold`.
3. Test on the Raspberry Pi: install with `deploy/install.sh`, then check the service status and the buzzer.
4. Consider a time-based PERCLOS and head-pose detection if the tuned version still misses events.
