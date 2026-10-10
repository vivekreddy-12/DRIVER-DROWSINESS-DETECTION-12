import threading

from alerts.audio import CompositeNotifier
from alerts.buzzer import GpioBuzzer
from detection.state import Level


class FakePin:
    def __init__(self):
        self.calls = []

    def set(self, on):
        self.calls.append(on)


class RecordingNotifier:
    def __init__(self):
        self.played = []

    def play(self, level):
        self.played.append(level)


def test_warning_pattern_turns_pin_on_then_off():
    pin = FakePin()
    GpioBuzzer(pin)._run([(0.01, 0.0)], threading.Event())
    assert pin.calls == [True, False]


def test_alert_pattern_has_two_beeps():
    pin = FakePin()
    GpioBuzzer(pin)._run([(0.01, 0.01), (0.01, 0.0)], threading.Event())
    assert pin.calls == [True, False, True, False]


def test_cancelled_pattern_does_not_touch_pin():
    pin = FakePin()
    cancel = threading.Event()
    cancel.set()
    GpioBuzzer(pin)._run([(0.5, 0.0)], cancel)
    assert pin.calls == [True]  # only the start of the first step, then it stops


def test_composite_forwards_to_every_output_even_if_one_fails():
    class Broken:
        def play(self, level):
            raise RuntimeError("boom")

    good = RecordingNotifier()
    CompositeNotifier(Broken(), good).play(Level.ALERT)
    assert good.played == [Level.ALERT]
