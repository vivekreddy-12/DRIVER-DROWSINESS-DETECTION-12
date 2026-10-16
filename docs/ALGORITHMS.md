# Algorithms and how each one behaves

This document describes every algorithm in the drowsiness assistant: what it computes, the rules it follows, its parameters, and how it behaves in practice. Parameter values come from `config.py` and the code. Behavior is described as the code implements it. None of it has been validated on real drivers yet.

Frame rate and timing depend on the device. The timing examples below use the simulated and unit-tested timelines.

---

## 1. Face landmark detection

**File:** `detection/landmarks.py`
**Method:** MediaPipe Face Mesh (the `mp.solutions.face_mesh` API, MediaPipe 0.10.14)

**What it does:** For each camera frame, it finds one face and returns 478 landmark points in pixel coordinates. The points cover the eyelids, eye corners, lips, and iris (because `refine_landmarks=True`).

**Working phenomena:**
- Each frame is converted from BGR to RGB before processing.
- Only one face is tracked (`max_num_faces=1`). If several people are in view, the tracker follows the most prominent face.
- Detection needs a confidence of at least 0.5. Tracking needs at least 0.5 between frames.
- If no face is found, `detect()` returns `None`. The rest of the pipeline then records "no face detected" and keeps the previous alert level.
- Normalized coordinates are scaled by the frame width and height, so the output matches the image size.

**Limits:** Sunglasses, a hand over the face, strong glare on glasses, a turned head, or low light can make the face disappear or shift the points.

---

## 2. Eye Aspect Ratio (EAR)

**File:** `detection/metrics.py`
**Reference:** Soukupová and Čech (2016)

**Formula:** For six eye points p1 to p6 (p1 and p4 are the corners, p2 and p3 the upper lid, p5 and p6 the lower lid):

```
EAR = (|p2 − p6| + |p3 − p5|) / (2 · |p1 − p4|)
```

**What it does:** It measures how open the eye is, relative to its width. The ratio does not depend on how far the face is from the camera.

**Working phenomena:**
- Open eyes give a value around 0.25 to 0.35 (about 0.30 in the code's example).
- Closing the eye drives the value toward 0. A fully closed eye is around 0.05 to 0.10.
- Blinks are short dips. A normal blink lasts about 100 to 400 ms, so it shows up as a brief dip below the threshold.
- The code averages the EAR of the left and right eyes. If the head turns, one eye can appear narrower, and the average smooths this out only partly.
- If the eye corners overlap, the width is zero and the function returns 0. This makes the eye look closed.

**Threshold:** `ear_threshold = 0.21`. Any frame with an average EAR below 0.21 counts as "eyes closed."

---

## 3. Mouth Aspect Ratio (MAR)

**File:** `detection/metrics.py`

**Formula:**
```
MAR = |upper lip − lower lip| / |left corner − right corner|
```

**What it does:** It measures how open the mouth is. A large value means the mouth is wide open, as in a yawn.

**Working phenomena:**
- A closed mouth gives a small value (about 0.1 in the code's example).
- Talking gives a fluctuating value, often between 0.2 and 0.5.
- A yawn gives a value of 0.6 or more, held for a period of time.
- If the corners overlap, the function returns 0.

**Threshold:** `mar_threshold = 0.6`.

---

## 4. Drowsiness state machine

**File:** `detection/state.py`
**Class:** `DrowsinessMonitor`

This is the core of the system. It takes one sample per frame (time, EAR, MAR, and optionally speed) and returns a `Status` with an alert level, a reason, and the current measurements. It keeps its own state between frames. Time comes in as a parameter, so the logic is testable without a clock.

### 4a. PERCLOS (percentage of eye closure)

**What it does:** It measures the share of recent frames in which the eyes were closed. It looks back over a rolling 60-second window.

**Rule:**
```
PERCLOS = (closed frames in the last 60 s) / (all frames in the last 60 s)
```

**Working phenomena:**
- Every frame adds one sample (time, closed or open). Samples older than 60 s are removed.
- It counts frames, not seconds. If the camera drops frames, the value shifts. For example, if frames slow to 10 per second, each closed frame weighs more than it did at 30 per second.
- PERCLOS rises slowly during a long closure and falls slowly after the eyes reopen. This makes it good at catching fatigue over time, and less good at reacting to a single closure.
- Blinks add only a little to PERCLOS, because each blink is short. A normal driver stays well below the threshold.
- Frames with no face are not added to the window. The window only holds frames where a face was found.

**Threshold:** `perclos_threshold = 0.35`. At 35% or more, a drowsy episode starts, even if no single closure has lasted 1.5 s.

### 4b. Eye closure timing

**What it does:** It measures how long the eyes have been continuously closed.

**Working phenomena:**
- When the EAR first drops below 0.21, the code records the time as `closed_since`.
- Each frame that stays below 0.21 keeps this timer running. As soon as one frame is above the threshold, the timer resets.
- A closure of 1.5 s or more (`eye_closed_onset_s`) starts a drowsy episode.

### 4c. Drowsy episode

**What it does:** It marks the period during which the driver is drowsy. Once started, an episode continues until the eyes have been open long enough.

**Start rule:** The episode starts when the eyes are closed **and** either:
- the continuous closure has reached 1.5 s, or
- PERCLOS has reached 35%.

**End rule:** The episode ends after 10 consecutive frames with open eyes (`recovery_frames = 10`). At 30 frames per second, this is about 0.33 s.

**Working phenomena:**
- The episode start time is the moment the rule is first satisfied. The alert level is measured from that time, not from when the eyes first closed. Since the eyes must be closed for 1.5 s before the rule is satisfied, the first warning comes 1.5 s after the eyes first close.
- A brief reopening during an episode does not end it. The driver must keep the eyes open for the full recovery period.
- If PERCLOS alone starts an episode, the reason text shows "drowsy (PERCLOS)" instead of "prolonged eye closure."

### 4d. Alert levels from episode length

**What it does:** It assigns a level based on how long the current episode has lasted.

| Episode length | Level | Reason shown |
|---|---|---|
| Under 4 s | WARNING | Prolonged eye closure, or drowsy (PERCLOS) |
| 4 s to under 8 s | ALERT | Same |
| 8 s or more | CRITICAL | Same |

**Working phenomena:**
- The level rises during a long episode. It drops to NORMAL when the episode ends.
- Within one episode the level only rises, because the episode length only grows. The one exception is the vehicle speed cap in section 4f, which can lower CRITICAL to ALERT while the car is stopped.

### 4e. Yawn counting

**What it does:** It counts yawns, and raises a warning when there are several in a short time.

**Rules:**
- A yawn starts when MAR goes to 0.6 or more.
- A yawn is counted when MAR drops back below 0.6, but only if the opening lasted at least 1 s (`yawn_min_duration_s`). Shorter openings are treated as speech.
- Yawns are kept for 5 minutes (`yawn_window_s = 300`). Older ones are dropped.
- Three yawns in that window (`yawn_count_threshold = 3`) raise a WARNING with the reason "frequent yawning."

**Working phenomena:**
- Yawns can raise a WARNING even when the eyes are open. This catches fatigue that does not yet show as eye closure.
- A yawn that is still in progress is not counted until it ends.
- A long conversation can produce several openings of 1 s or more. Since the threshold is three yawns in five minutes, this is a known source of false warnings.

### 4f. Vehicle speed cap

**What it does:** It stops a stationary vehicle from getting the pull-over prompt.

**Rule:** If the level is CRITICAL, the speed is known, and the speed is below 10 km/h (`min_speed_kmh_for_critical = 10`), the level is lowered to ALERT. The reason gets " (vehicle stopped)" added.

**Working phenomena:**
- If no speed reading is available (no OBD-II adapter), no cap is applied, and CRITICAL stays as CRITICAL.
- The cap only changes the level. It does not stop the episode. Once the vehicle moves, the level returns to CRITICAL if the episode is still long enough.

### 4g. Missing face

**Rule:** When there is no face in the frame, the monitor does not change its state. It returns the last status with the reason changed to "no face detected."

**Working phenomena:**
- The alert level is held. If a driver turns away during an episode and the face disappears, the level stays where it was.
- The episode timers and PERCLOS window do not advance during this time. When the face returns, the state continues from where it stopped.

---

## 5. Alert escalation controller

**File:** `alerts/escalation.py`
**Class:** `AlertController`

**What it does:** It decides when to send an alert to the outputs, and how often to repeat it.

**Rules:**
- **Immediate on escalation:** When the level goes up (for example from WARNING to ALERT), the alert fires right away.
- **Repeats:** While the level stays the same, the alert fires again after a set interval:

| Level | Repeat interval |
|---|---|
| WARNING | 6 s |
| ALERT | 3 s |
| CRITICAL | 2 s |

- **Clear:** When the level returns to NORMAL, the controller calls `stop()` on the outputs, so any ongoing siren stops.

**Working phenomena:**
- On a Windows laptop, repeat calls for the same level do not restart the siren. It plays for 10 seconds and then stays quiet (see section 6b).
- A level that drops (for example from CRITICAL to ALERT) does not fire immediately. It waits for the repeat interval.
- The first alert of an episode usually fires as soon as the level becomes WARNING. For an eye-closure episode, that is 1.5 s after the eyes first close.

---

## 6. Alert outputs

### 6a. Terminal bell, console message, and speech

**File:** `alerts/audio.py`

- **Bell and console:** Every alert prints a line such as `[ALERT ALERT] You seem drowsy. Please take a break.` and sends a terminal bell character.
- **Speech:** If `pyttsx3` is installed, the message is spoken in a background thread. Only one speech job runs at a time. A new alert that arrives while speaking is skipped. A new engine is created for each message.
- **Messages:**
  - WARNING: "Stay alert."
  - ALERT: "You seem drowsy. Please take a break."
  - CRITICAL: "Wake up. Pull over safely now."

**Working phenomena:** Speech never blocks the camera loop. If speech fails, the error is printed and detection continues.

### 6b. Laptop siren (Windows)

**File:** `alerts/beep.py`
**Method:** `winsound.Beep`, which plays through the system sound output

| Level | Sound | Length |
|---|---|---|
| WARNING | One 880 Hz beep, 0.15 s | One beep |
| ALERT | Siren alternating 1200 Hz and 1500 Hz, 0.5 s each, with 0.15 s gaps | Runs for 10 s, then stops |
| CRITICAL | Faster siren alternating 1800 Hz and 2400 Hz, 0.25 s each | Runs for 10 s, then stops |

**Working phenomena:**
- Each siren runs on its own background thread, so the camera loop never waits.
- A siren does not restart while the same level is active. After 10 s, it stays silent until the level changes or the episode clears.
- A new level (ALERT to CRITICAL, for example) starts a new 10-second siren.
- A WARNING beep is skipped while a siren is playing.
- On systems without `winsound` (Linux, macOS, Raspberry Pi), the notifier does nothing.
- The volume is set by the system volume. The code cannot make the sound louder than that.

### 6c. GPIO buzzer (Raspberry Pi)

**File:** `alerts/buzzer.py`
**Method:** `gpiozero.DigitalOutputDevice` on the chosen pin (default GPIO 17 in the service file)

| Level | Pattern |
|---|---|
| WARNING | One 0.15 s pulse |
| ALERT | Two 0.3 s pulses, 0.2 s apart |
| CRITICAL | Three 0.4 s pulses, 0.2 s apart |

**Working phenomena:**
- Each pattern runs on a background thread.
- A new alert cancels the pattern that is still playing, so the newest alert is always heard.
- Pulses are on or off only. The buzzer does not pulse at a set frequency.
- If the pin cannot be opened, the program continues without the buzzer.

### 6d. Combined output

**File:** `alerts/audio.py`, class `CompositeNotifier`

- Each alert goes to every enabled output (bell and console, speech, siren, buzzer).
- If one output fails, the error is printed and the other outputs still run.
- The `stop()` call is passed to every output that has one.

---

## 7. Vehicle speed (OBD-II)

**File:** `vehicle/obd.py`
**Method:** `python-obd` over an ELM327 adapter (USB or Bluetooth)

**Working phenomena:**
- The adapter is queried for the SPEED command at most once per second (`speed_poll_interval_s = 1.0`). Between queries, the last value is reused.
- If the adapter is not connected, speed is `None` and the cap in section 4f does not apply.
- If a query fails or returns no data, the speed is `None` for that query.
- The connection is opened without fast mode, so each query waits for the adapter's response.

---

## 8. CSV telemetry

**File:** `telemetry/logger.py`

**What it does:** It writes one row for each processed frame, for later analysis and threshold tuning.

**Columns:** `t, ear, mar, perclos, closed_for_s, yawns, speed_kmh, level, reason`

**Working phenomena:**
- A header row is written once, when the file is new or empty.
- Each row is flushed to disk immediately, so the file is up to date even if the program stops suddenly.
- Missing values (no face, no speed) are written as empty fields.
- The file grows by about one row per frame, so a long drive can produce a large file.

---

## 9. Main loop

**File:** `main.py`

**Working order for each frame:**
1. Read a frame from the camera.
2. Find the face landmarks.
3. Compute EAR and MAR from the landmarks (or pass `None` if no face).
4. Read the current speed (from the cache, if polled recently).
5. Update the drowsiness state machine.
6. Pass the status to the alert controller.
7. Write the CSV row.
8. Draw the overlay and show the window (unless `--no-display` is set).

**Shutdown:** Pressing `q` in the window, Ctrl+C, or SIGTERM from systemd all run the same cleanup. The camera, face tracker, OBD connection, and log file are closed.

---

## 10. Worked timeline

The following example comes from the scripted simulation in `make_cinematic.py`, which runs the same code as the product.

| Time | What happens | Level |
|---|---|---|
| 0 to 12 s | Normal blinks (EAR dips for about 0.2 s every 4 s) | NORMAL |
| 12 to 13.8 s | One yawn (MAR 0.82 for 1.8 s), counted when the mouth closes | NORMAL (one yawn) |
| 25.0 s | Eyes close (EAR 0.09) | NORMAL |
| 26.5 s | Eyes have been closed 1.5 s, so the episode starts | WARNING (one beep) |
| 30.5 s | Episode has lasted 4 s | ALERT (10 s siren) |
| 31.0 s | Eyes reopen. The episode continues until 10 frames are open | ALERT |
| 40.0 s | Second closure begins | NORMAL |
| 41.3 s | Second episode starts | WARNING |
| 45.3 s | Episode has lasted 4 s | ALERT (siren) |
| 49.3 s | Episode has lasted 8 s | CRITICAL (faster siren) |
| 52.0 s | Eyes reopen | Episode ends after the recovery period |

---

## 11. Known limitations

- **Frame-based measurement:** PERCLOS and the timers depend on the frame rate. A slow or irregular frame rate changes the results.
- **No head-pose detection:** Nodding and head drop are not detected.
- **Blinks reset the closure timer:** A blink above the threshold restarts the 1.5 s count. Long, slow closures are caught, but patterns of short closures that stay under 1.5 s may be missed by the timer. PERCLOS covers these.
- **Yawn false positives:** Conversation can produce long mouth openings, which may trigger a yawn warning.
- **Fixed thresholds:** EAR and MAR depend on the face, glasses, and lighting. The default thresholds have not been tuned for any particular driver or camera.
- **Missing face holds the level:** A driver who looks away during an episode keeps the last level until the face returns.
- **Siren limited to 10 s:** After the siren stops, the driver gets no further sound until the level changes or the episode clears, even if drowsiness continues.

---

## 12. Testing

The unit tests in `tests/` check the algorithms without a camera:
- `test_metrics.py`: EAR and MAR formulas on synthetic points.
- `test_state.py`: episode timing, PERCLOS, yawn counting, the speed cap, and missing-face handling.
- `test_alerts.py`: escalation timing, repeat intervals, and the stop call.
- `test_buzzer.py`: buzzer patterns, cancellation, and output isolation.
- `test_beep.py`: siren duration, restart rules, and that playback never blocks the camera loop.

All 32 tests pass. They confirm that the code does what it is designed to do. They do not confirm that the thresholds suit a real driver.
