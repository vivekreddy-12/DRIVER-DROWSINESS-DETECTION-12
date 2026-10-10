from config import DEFAULT
from detection.state import DrowsinessMonitor, Level

OPEN_EAR = 0.30
CLOSED_EAR = 0.10
NORMAL_MAR = 0.10
YAWN_MAR = 0.80
FPS = 10


def feed(monitor, t0, seconds, ear, mar, speed=None):
    """Feed frames at FPS for `seconds`. Returns (last status, next timestamp)."""
    t = t0
    status = None
    for _ in range(int(round(seconds * FPS))):
        status = monitor.update(t, ear, mar, speed)
        t += 1 / FPS
    return status, t


def test_awake_driver_stays_normal():
    mon = DrowsinessMonitor()
    status, _ = feed(mon, 0.0, 20, OPEN_EAR, NORMAL_MAR)
    assert status.level == Level.NORMAL
    assert status.perclos == 0.0


def test_long_closure_raises_warning():
    mon = DrowsinessMonitor()
    _, t = feed(mon, 0.0, 2.0, OPEN_EAR, NORMAL_MAR)
    status, _ = feed(mon, t, DEFAULT.eye_closed_onset_s + 0.5, CLOSED_EAR, NORMAL_MAR)
    assert status.level >= Level.WARNING


def test_escalates_to_critical_with_speed_unknown():
    mon = DrowsinessMonitor()
    _, t = feed(mon, 0.0, 2.0, OPEN_EAR, NORMAL_MAR)
    status, _ = feed(mon, t, DEFAULT.critical_after_s + 4.0, CLOSED_EAR, NORMAL_MAR)
    assert status.level == Level.CRITICAL


def test_critical_is_capped_at_alert_when_vehicle_stopped():
    mon = DrowsinessMonitor()
    _, t = feed(mon, 0.0, 2.0, OPEN_EAR, NORMAL_MAR, speed=0.0)
    status, _ = feed(mon, t, DEFAULT.critical_after_s + 4.0, CLOSED_EAR, NORMAL_MAR, speed=0.0)
    assert status.level == Level.ALERT
    assert "vehicle stopped" in status.reason


def test_episode_clears_after_eyes_reopen():
    mon = DrowsinessMonitor()
    _, t = feed(mon, 0.0, 2.0, OPEN_EAR, NORMAL_MAR)
    _, t = feed(mon, t, 2.0, CLOSED_EAR, NORMAL_MAR)
    status, _ = feed(mon, t, 1.5, OPEN_EAR, NORMAL_MAR)
    assert status.level == Level.NORMAL


def test_frequent_yawns_raise_warning():
    mon = DrowsinessMonitor()
    t = 0.0
    status = None
    for _ in range(DEFAULT.yawn_count_threshold):
        status, t = feed(mon, t, 1.5, OPEN_EAR, YAWN_MAR)
        status, t = feed(mon, t, 2.0, OPEN_EAR, NORMAL_MAR)
    assert status.yawns == DEFAULT.yawn_count_threshold
    assert status.level == Level.WARNING
    assert status.reason == "frequent yawning"


def test_short_mouth_opening_is_not_a_yawn():
    mon = DrowsinessMonitor()
    t = 0.0
    status = None
    for _ in range(5):
        status, t = feed(mon, t, 0.3, OPEN_EAR, YAWN_MAR)  # talking, not yawning
        status, t = feed(mon, t, 1.0, OPEN_EAR, NORMAL_MAR)
    assert status.yawns == 0


def test_missing_face_keeps_level_and_reports_reason():
    mon = DrowsinessMonitor()
    _, t = feed(mon, 0.0, 2.0, OPEN_EAR, NORMAL_MAR)
    status = mon.update(t, None, None)
    assert status.reason == "no face detected"
    assert status.level == Level.NORMAL
