"""Drowsiness state machine.

Feed it one sample per frame (timestamp, eye aspect ratio, mouth aspect ratio,
and optionally speed). It keeps a rolling PERCLOS window, tracks how long an
episode of drowsiness has lasted, counts yawns, and returns a Status with an
alert level.

Timestamps are passed in, not read from the clock, so the logic can be tested.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from enum import IntEnum

from config import DEFAULT, Config


class Level(IntEnum):
    NORMAL = 0
    WARNING = 1    # chime and on-screen cue
    ALERT = 2      # spoken prompt to take a break
    CRITICAL = 3   # repeated alarm and a prompt to pull over


@dataclass(frozen=True)
class Status:
    level: Level = Level.NORMAL
    ear: float | None = None
    mar: float | None = None
    perclos: float = 0.0
    closed_for_s: float = 0.0
    yawns: int = 0
    reason: str = "starting"


class DrowsinessMonitor:
    def __init__(self, cfg: Config = DEFAULT) -> None:
        self.cfg = cfg
        self._samples: deque[tuple[float, bool]] = deque()   # (time, eyes closed)
        self._closed_since: float | None = None
        self._open_streak = 0
        self._episode_start: float | None = None
        self._yawn_start: float | None = None
        self._yawn_times: deque[float] = deque()
        self._last = Status()

    def update(
        self,
        t: float,
        ear: float | None,
        mar: float | None,
        speed_kmh: float | None = None,
    ) -> Status:
        """Process one frame. Pass ear=None when no face was found."""
        if ear is None or mar is None:
            # Keep the previous level, but say the face is missing.
            self._last = replace(self._last, reason="no face detected")
            return self._last

        cfg = self.cfg
        closed = ear < cfg.ear_threshold

        # PERCLOS: share of samples in the rolling window with eyes closed.
        self._samples.append((t, closed))
        while self._samples and t - self._samples[0][0] > cfg.perclos_window_s:
            self._samples.popleft()
        perclos = sum(1 for _, c in self._samples if c) / len(self._samples)

        # Continuous closure.
        if closed:
            if self._closed_since is None:
                self._closed_since = t
            self._open_streak = 0
        else:
            self._closed_since = None
            self._open_streak += 1
        closed_for = 0.0 if self._closed_since is None else t - self._closed_since

        # Start an episode while eyes are closed and either the closure is long
        # or PERCLOS is high. End it after recovery_frames of open eyes.
        if self._episode_start is None:
            if closed and (closed_for >= cfg.eye_closed_onset_s or perclos >= cfg.perclos_threshold):
                self._episode_start = t
        elif self._open_streak >= cfg.recovery_frames:
            self._episode_start = None

        # Yawns: count openings of the mouth that last at least yawn_min_duration_s.
        yawning = mar >= cfg.mar_threshold
        if yawning and self._yawn_start is None:
            self._yawn_start = t
        elif not yawning and self._yawn_start is not None:
            if t - self._yawn_start >= cfg.yawn_min_duration_s:
                self._yawn_times.append(t)
            self._yawn_start = None
        while self._yawn_times and t - self._yawn_times[0] > cfg.yawn_window_s:
            self._yawn_times.popleft()
        yawns = len(self._yawn_times)

        # Level and reason.
        level = Level.NORMAL
        reason = "normal"
        if self._episode_start is not None:
            duration = t - self._episode_start
            if duration >= cfg.critical_after_s:
                level = Level.CRITICAL
            elif duration >= cfg.alert_after_s:
                level = Level.ALERT
            else:
                level = Level.WARNING
            reason = "prolonged eye closure" if closed_for >= cfg.eye_closed_onset_s else "drowsy (PERCLOS)"

        if yawns >= cfg.yawn_count_threshold and level < Level.WARNING:
            level = Level.WARNING
            reason = "frequent yawning"

        # A stopped vehicle should not get the pull-over prompt.
        if (
            level is Level.CRITICAL
            and speed_kmh is not None
            and speed_kmh < cfg.min_speed_kmh_for_critical
        ):
            level = Level.ALERT
            reason += " (vehicle stopped)"

        self._last = Status(
            level=level,
            ear=ear,
            mar=mar,
            perclos=perclos,
            closed_for_s=closed_for,
            yawns=yawns,
            reason=reason,
        )
        return self._last
