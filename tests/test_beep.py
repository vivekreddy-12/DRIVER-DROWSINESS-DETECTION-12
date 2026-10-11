import threading
import time

from alerts.beep import BEEP_PATTERNS, BeepNotifier
from detection.state import Level


def wait_for(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def test_alert_plays_two_beeps_at_expected_pitch_and_length():
    played = []
    notifier = BeepNotifier(tone=lambda hz, ms: played.append((hz, ms)), sleep=lambda s: None)
    notifier.play(Level.ALERT)
    assert wait_for(lambda: len(played) == 2)
    assert played == [(1000, 300), (1000, 300)]


def test_critical_plays_three_beeps():
    played = []
    notifier = BeepNotifier(tone=lambda hz, ms: played.append((hz, ms)), sleep=lambda s: None)
    notifier.play(Level.CRITICAL)
    assert wait_for(lambda: len(played) == len(BEEP_PATTERNS[Level.CRITICAL]))


def test_normal_level_plays_nothing():
    played = []
    notifier = BeepNotifier(tone=lambda hz, ms: played.append((hz, ms)), sleep=lambda s: None)
    notifier.play(Level.NORMAL)
    time.sleep(0.05)
    assert played == []


def test_play_returns_immediately_even_while_sound_is_playing():
    release = threading.Event()

    def slow_tone(hz, ms):
        release.wait(timeout=2.0)

    notifier = BeepNotifier(tone=slow_tone, sleep=lambda s: None)
    start = time.monotonic()
    for _ in range(10):
        notifier.play(Level.WARNING)
    elapsed = time.monotonic() - start
    release.set()
    assert elapsed < 0.5


def test_without_windows_sound_the_notifier_is_disabled_and_safe():
    notifier = BeepNotifier(tone=None)
    if notifier.available:
        # Running on Windows: the real winsound module was found. Nothing to check here.
        return
    notifier.play(Level.CRITICAL)  # must not raise
