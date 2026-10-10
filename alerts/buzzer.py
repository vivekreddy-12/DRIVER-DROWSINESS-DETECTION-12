"""GPIO buzzer output for Raspberry Pi.

Each alert level plays a short pattern on a GPIO pin. Patterns run in a
background thread, so the camera loop never waits. A new alert cancels the
pattern that is still playing.
"""
from __future__ import annotations

import threading
from typing import Protocol

from detection.state import Level

# Steps of (on_seconds, off_seconds). Each alert is re-triggered by the
# escalation controller while the condition lasts.
PATTERNS: dict[Level, list[tuple[float, float]]] = {
    Level.WARNING: [(0.15, 0.0)],
    Level.ALERT: [(0.3, 0.2), (0.3, 0.0)],
    Level.CRITICAL: [(0.4, 0.2), (0.4, 0.2), (0.4, 0.0)],
}


class PinDriver(Protocol):
    def set(self, on: bool) -> None: ...


class GpioPin:
    """Drives a pin with gpiozero. Only works on a Raspberry Pi (or other supported board)."""

    def __init__(self, pin: int) -> None:
        from gpiozero import DigitalOutputDevice  # imported here so the rest runs without GPIO

        self._device = DigitalOutputDevice(pin, initial_value=False)

    def set(self, on: bool) -> None:
        self._device.value = on


class GpioBuzzer:
    def __init__(self, driver: PinDriver) -> None:
        self._driver = driver
        self._lock = threading.Lock()
        self._cancel = threading.Event()

    def play(self, level: Level) -> None:
        pattern = PATTERNS.get(level)
        if pattern is None:
            return
        with self._lock:
            self._cancel.set()                 # stop a pattern that is still running
            self._cancel = threading.Event()
            threading.Thread(target=self._run, args=(pattern, self._cancel), daemon=True).start()

    def _run(self, pattern: list[tuple[float, float]], cancel: threading.Event) -> None:
        # If cancelled, return without touching the pin: the new pattern owns it now.
        for on_s, off_s in pattern:
            self._driver.set(True)
            if cancel.wait(on_s):
                return
            self._driver.set(False)
            if off_s and cancel.wait(off_s):
                return
