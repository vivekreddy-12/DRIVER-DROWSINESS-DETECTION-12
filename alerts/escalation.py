"""Decides when to fire an alert, and how often to repeat it while it continues.

Kept separate from the audio output so it can be tested with a fake notifier.
"""
from __future__ import annotations

from typing import Protocol

from detection.state import Level, Status

# Seconds between repeats while the level stays the same.
REPEAT_INTERVAL_S = {
    Level.WARNING: 6.0,
    Level.ALERT: 3.0,
    Level.CRITICAL: 2.0,
}


class Notifier(Protocol):
    def play(self, level: Level) -> None: ...


class AlertController:
    def __init__(self, notifier: Notifier) -> None:
        self._notifier = notifier
        self._level = Level.NORMAL
        self._last_fired = float("-inf")

    def handle(self, t: float, status: Status) -> None:
        level = status.level
        if level == Level.NORMAL:
            if self._level != Level.NORMAL:
                # Let outputs that loop (such as the siren) know the alert has cleared.
                stop = getattr(self._notifier, "stop", None)
                if stop is not None:
                    stop()
            self._level = Level.NORMAL
            return

        # Fire immediately on escalation, otherwise fire again after the repeat interval.
        escalated = level > self._level
        repeat_due = t - self._last_fired >= REPEAT_INTERVAL_S[level]
        if escalated or repeat_due:
            self._notifier.play(level)
            self._last_fired = t
        self._level = level
