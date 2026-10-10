"""Alarm output: terminal bell, console message, and optional speech.

Speech uses pyttsx3 if it is installed. It runs in a background thread so the
camera loop never blocks. In a real vehicle, replace or extend play() to drive
a buzzer through GPIO or a car audio input.
"""
from __future__ import annotations

import sys
import threading

from detection.state import Level

MESSAGES = {
    Level.WARNING: "Stay alert.",
    Level.ALERT: "You seem drowsy. Please take a break.",
    Level.CRITICAL: "Wake up. Pull over safely now.",
}


class CompositeNotifier:
    """Sends each alert to several outputs. One failing output does not stop the others."""

    def __init__(self, *notifiers) -> None:
        self._notifiers = notifiers

    def play(self, level: Level) -> None:
        for notifier in self._notifiers:
            try:
                notifier.play(level)
            except Exception as exc:
                print(f"[alerts] output failed: {exc}", file=sys.stderr)


class Notifier:
    def __init__(self, voice: bool = True) -> None:
        self._tts = None
        self._speaking = threading.Lock()
        if voice:
            try:
                import pyttsx3  # noqa: F401  (checked here, used in _speak)
                self._tts = pyttsx3
            except ImportError:
                print("[alerts] pyttsx3 not installed, speech disabled", file=sys.stderr)

    def play(self, level: Level) -> None:
        message = MESSAGES.get(level)
        if message is None:
            return
        sys.stdout.write("\a")  # terminal bell
        sys.stdout.flush()
        print(f"[ALERT {level.name}] {message}", flush=True)
        if self._tts is not None and self._speaking.acquire(blocking=False):
            threading.Thread(target=self._speak, args=(message,), daemon=True).start()

    def _speak(self, message: str) -> None:
        try:
            engine = self._tts.init()  # new engine per call avoids cross-thread issues
            engine.say(message)
            engine.runAndWait()
        except Exception as exc:  # speech failure must never stop detection
            print(f"[alerts] speech failed: {exc}", file=sys.stderr)
        finally:
            self._speaking.release()
