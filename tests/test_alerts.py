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


class StoppableNotifier(FakeNotifier):
    def __init__(self):
        super().__init__()
        self.stops = 0

    def stop(self):
        self.stops += 1


def test_stop_is_called_once_when_alert_clears():
    notifier = StoppableNotifier()
    ctrl = AlertController(notifier)
    ctrl.handle(0.0, status(Level.ALERT))
    ctrl.handle(1.0, status(Level.NORMAL))
    ctrl.handle(2.0, status(Level.NORMAL))  # already normal: no second stop
    assert notifier.stops == 1


def test_notifier_without_stop_still_works():
    notifier = FakeNotifier()
    ctrl = AlertController(notifier)
    ctrl.handle(0.0, status(Level.ALERT))
    ctrl.handle(1.0, status(Level.NORMAL))
    assert notifier.played == [Level.ALERT]


def test_normal_status_never_fires():
    notifier = FakeNotifier()
    ctrl = AlertController(notifier)
    for t in range(5):
        ctrl.handle(float(t), status(Level.NORMAL))
    assert notifier.played == []
