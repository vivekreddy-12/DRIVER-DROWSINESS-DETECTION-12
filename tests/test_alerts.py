from alerts.escalation import AlertController
from detection.state import Level, Status


class FakeNotifier:
    def __init__(self):
        self.played = []

    def play(self, level):
        self.played.append(level)


def status(level):
    return Status(level=level)


def test_fires_on_escalation_and_respects_repeat_interval():
    notifier = FakeNotifier()
    ctrl = AlertController(notifier)

    ctrl.handle(0.0, status(Level.WARNING))   # fires: first warning
    ctrl.handle(1.0, status(Level.WARNING))   # too soon to repeat
    ctrl.handle(1.5, status(Level.ALERT))     # fires: escalation is immediate
    ctrl.handle(2.0, status(Level.ALERT))     # too soon to repeat
    ctrl.handle(4.6, status(Level.ALERT))     # repeat interval has passed

    assert notifier.played == [Level.WARNING, Level.ALERT, Level.ALERT]


def test_normal_status_never_fires():
    notifier = FakeNotifier()
    ctrl = AlertController(notifier)
    for t in range(5):
        ctrl.handle(float(t), status(Level.NORMAL))
    assert notifier.played == []
