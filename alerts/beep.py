"""Loud alarm through the laptop speakers (Windows).

Uses the built-in winsound module, so no extra packages are needed.

- WARNING plays one short beep.
- ALERT and CRITICAL start a siren that sounds for ALARM_DURATION_S (10 seconds)
  and then stops. It does not restart while the same alert continues. It
  restarts only if the level changes, or after stop() is called when the
  drowsiness episode clears.

Sounds run on background threads, so the camera loop never waits.

On systems without winsound (Linux, macOS, Raspberry Pi), this notifier does
nothing. The bell, speech, and GPIO buzzer outputs still work.
"""
from __future__ import annotations

import sys
import threading
import time
from typing import Callable

from detection.state import Level

# Each step is (frequency in Hz, duration in seconds, pause after in seconds).
WARNING_BEEP: list[tuple[int, float, float]] = [(880, 0.15, 0.0)]

# Repeating siren patterns. The loop runs until stop() is called.
ALARM_PATTERNS: dict[Level, list[tuple[int, float, float]]] = {
    Level.ALERT: [(1200, 0.5, 0.15), (1500, 0.5, 0.15)],
    Level.CRITICAL: [(1800, 0.25, 0.0), (2400, 0.25, 0.0)],
}

# How long one alert's siren sounds before it stops.
ALARM_DURATION_S = 10.0

ToneFn = Callable[[int, int], None]  # (frequency in Hz, duration in ms)


def _windows_tone() -> ToneFn | None:
    try:
        import winsound
    except ImportError:
        return None
    return winsound.Beep


class BeepNotifier:
    def __init__(self, tone: ToneFn | None = None, alarm_duration_s: float = ALARM_DURATION_S) -> None:
        self._tone = tone if tone is not None else _windows_tone()
        self._alarm_duration_s = alarm_duration_s
        self._lock = threading.Lock()
        self._alarm_level: Level | None = None
        self._alarm_stop: threading.Event | None = None
        self.available = self._tone is not None
        if not self.available:
            print("[beep] sound is only available on Windows; continuing without it", file=sys.stderr)

    def play(self, level: Level) -> None:
        if not self.available:
            return
        if level in ALARM_PATTERNS:
            self._start_alarm(level)
        elif level == Level.WARNING:
            with self._lock:
                if self._alarm_level is not None:
                    return  # the louder alarm is already sounding
            threading.Thread(target=self._play_once, args=(WARNING_BEEP,), daemon=True).start()

    def stop(self) -> None:
        """Stop the repeating alarm. Safe to call when no alarm is running."""
        with self._lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        if self._alarm_stop is not None:
            self._alarm_stop.set()
        self._alarm_stop = None
        self._alarm_level = None

    def _start_alarm(self, level: Level) -> None:
        with self._lock:
            if self._alarm_level == level:
                return  # already sounding this level
            self._stop_locked()
            stop = threading.Event()
            self._alarm_stop = stop
            self._alarm_level = level
        threading.Thread(target=self._alarm_loop, args=(ALARM_PATTERNS[level], stop), daemon=True).start()

    def _alarm_loop(self, pattern: list[tuple[int, float, float]], stop: threading.Event) -> None:
        deadline = time.monotonic() + self._alarm_duration_s
        while not stop.is_set() and time.monotonic() < deadline:
            if not self._play_steps(pattern, stop):
                return

    def _play_once(self, pattern: list[tuple[int, float, float]]) -> None:
        self._play_steps(pattern, threading.Event())

    def _play_steps(self, pattern: list[tuple[int, float, float]], stop: threading.Event) -> bool:
        """Play one pass of the pattern. Returns False if it was stopped or failed."""
        for frequency, duration, pause in pattern:
            if stop.is_set():
                return False
            try:
                self._tone(frequency, int(duration * 1000))
            except Exception as exc:  # sound failure must never stop detection
                print(f"[beep] could not play sound: {exc}", file=sys.stderr)
                return False
            if pause:
                stop.wait(pause)
        return True
