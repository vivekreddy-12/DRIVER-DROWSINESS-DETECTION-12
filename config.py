"""Tunable thresholds for the drowsiness assistant.

Change values here instead of inside the detection code. Log files written
by telemetry/logger.py let you check how these values behave on real drives.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Camera
    camera_index: int = 0
    frame_width: int = 640
    frame_height: int = 480

    # Eye closure
    ear_threshold: float = 0.21          # EAR below this counts as "eyes closed"
    eye_closed_onset_s: float = 1.5      # continuous closure that starts a drowsy episode
    perclos_window_s: float = 60.0       # rolling window for PERCLOS
    perclos_threshold: float = 0.35      # fraction of closed time that signals fatigue
    recovery_frames: int = 10            # consecutive open-eye frames to end an episode

    # Yawning
    mar_threshold: float = 0.6           # mouth aspect ratio above this = mouth open
    yawn_min_duration_s: float = 1.0     # shorter openings are talking, not yawns
    yawn_window_s: float = 300.0         # window for counting yawns
    yawn_count_threshold: int = 3        # yawns in the window that trigger a warning

    # Escalation, measured from the start of a drowsy episode
    alert_after_s: float = 4.0
    critical_after_s: float = 8.0

    # Vehicle speed
    min_speed_kmh_for_critical: float = 10.0   # below this, CRITICAL is capped at ALERT
    speed_poll_interval_s: float = 1.0


DEFAULT = Config()
