"""Beep sound through the laptop speakers (Windows).

Uses the built-in winsound module, so no extra packages are needed. Each alert
level plays its own tone pattern, with a higher pitch for a more serious level.

Beeps run on one background thread, so the camera loop never waits. If a beep
is still playing when a new alert arrives, the new one queues behind it. If the
queue is full, the oldest queued beep is dropped so the newest alert is heard.

On systems without winsound (Linux, macOS, Raspberry Pi), this notifier does
nothing. The bell, speech, and GPIO buzzer outputs still work.
"""
from __future__ import annotations

import queue
import sys
import threading
import time
from typing import Callable

from detection.state import Level

# Each step is (frequency in Hz, duration in seconds, pause after in seconds).
BEEP_PATTERNS: dict[Level, list[tuple[int, float, float]]] = {
    Level.WARNING: [(880, 0.15, 0.0)],
    Level.ALERT: [(1000, 0.3, 0.2), (1000, 0.3, 0.0)],
    Level.CRITICAL: [(1200, 0.4, 0.2), (1200, 0.4, 0.2), (1200, 0.4, 0.0)],
}

ToneFn = Callable[[int, int], None]  # (frequency in Hz, duration in ms)


def _windows_tone() -> ToneFn | None:
    try:
        import winsound
    except ImportError:
        return None
    return winsound.Beep


class BeepNotifier:
    def __init__(
        self,
        tone: ToneFn | None = None,
        queue_size: int = 4,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._tone = tone if tone is not None else _windows_tone()
        self._sleep = sleep
        self._queue: queue.Queue[Level] = queue.Queue(maxsize=queue_size)
        self.available = self._tone is not None
        if self.available:
            threading.Thread(target=self._worker, daemon=True).start()
        else:
            print("[beep] sound is only available on Windows; continuing without it", file=sys.stderr)

    def play(self, level: Level) -> None:
        if not self.available or level not in BEEP_PATTERNS:
            return
        try:
            self._queue.put_nowait(level)
        except queue.Full:
            try:
                self._queue.get_nowait()   # drop the oldest queued beep
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(level)
            except queue.Full:
                pass

    def _worker(self) -> None:
        while True:
            level = self._queue.get()
            for frequency, duration, pause in BEEP_PATTERNS[level]:
                try:
                    self._tone(frequency, int(duration * 1000))
                except Exception as exc:  # sound failure must never stop detection
                    print(f"[beep] could not play sound: {exc}", file=sys.stderr)
                    break
                if pause:
                    self._sleep(pause)
