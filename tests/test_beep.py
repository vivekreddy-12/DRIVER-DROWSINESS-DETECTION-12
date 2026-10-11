import threading
import time

from alerts.beep import ALARM_PATTERNS, BeepNotifier
from detection.state import Level


def wait_for(condition, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


def recorder():
    played = []
    return played, lambda hz, ms: played.append((hz, ms))


def test_warning_plays_one_short_beep():
    played, tone = recorder()
    notifier = BeepNotifier(tone=tone)
    notifier.play(Level.WARNING)
    assert wait_for(lambda: len(played) == 1)
    time.sleep(0.05)
    assert played == [(880, 150)]


def test_alert_siren_repeats_until_stopped():
    played, tone = recorder()
    notifier = BeepNotifier(tone=tone)
    notifier.play(Level.ALERT)
    assert wait_for(lambda: len(played) >= 4)  # more than one full pass of the pattern
    notifier.stop()
    time.sleep(0.2)                            # let any in-progress tone finish
    count = len(played)
    time.sleep(0.3)
    assert len(played) == count                # no more tones after stop()


def test_critical_uses_faster_siren_than_alert():
    assert ALARM_PATTERNS[Level.CRITICAL][0][0] > ALARM_PATTERNS[Level.ALERT][0][0]
    played, tone = recorder()
    notifier = BeepNotifier(tone=tone)
    notifier.play(Level.CRITICAL)
    assert wait_for(lambda: len(played) >= 2)
    notifier.stop()


def test_normal_level_plays_nothing():
    played, tone = recorder()
    notifier = BeepNotifier(tone=tone)
    notifier.play(Level.NORMAL)
    time.sleep(0.05)
    assert played == []


def test_warning_is_skipped_while_alarm_is_sounding():
    played, tone = recorder()
    notifier = BeepNotifier(tone=tone)
    notifier.play(Level.ALERT)
    assert wait_for(lambda: len(played) >= 1)
    before = len(played)
    notifier.play(Level.WARNING)
    time.sleep(0.2)
    assert all(hz != 880 for hz, _ in played[before:])  # no warning beep during the alarm
    notifier.stop()


def test_play_returns_immediately_even_while_sound_is_playing():
    release = threading.Event()

    def slow_tone(hz, ms):
        release.wait(timeout=2.0)

    notifier = BeepNotifier(tone=slow_tone)
    start = time.monotonic()
    for level in (Level.ALERT, Level.CRITICAL, Level.WARNING, Level.ALERT):
        notifier.play(level)
    elapsed = time.monotonic() - start
    release.set()
    notifier.stop()
    assert elapsed < 0.5


def test_without_windows_sound_the_notifier_is_disabled_and_safe():
    notifier = BeepNotifier(tone=None)
    if notifier.available:
        # Running on Windows: the real winsound module was found. Nothing to check here.
        return
    notifier.play(Level.CRITICAL)  # must not raise
    notifier.stop()
