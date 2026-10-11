"""Driver drowsiness assistant: entry point.

Examples:
    python main.py                          # default camera, on-screen display, speech if available
    python main.py --obd-port /dev/rfcomm0  # add vehicle speed from an OBD-II adapter
    python main.py --no-display --log drive.csv   # headless, log every frame to CSV
"""
from __future__ import annotations

import argparse
import sys
import time

import cv2
import numpy as np

import signal

from alerts.audio import CompositeNotifier, Notifier
from alerts.beep import BeepNotifier
from alerts.buzzer import GpioBuzzer, GpioPin
from alerts.escalation import AlertController
from config import DEFAULT
from detection.metrics import average_ear, mouth_aspect_ratio
from detection.state import Level, Status
from detection.state import DrowsinessMonitor
from telemetry.logger import CsvLogger
from vehicle.obd import SpeedSource

COLORS = {
    Level.NORMAL: (60, 160, 60),
    Level.WARNING: (0, 190, 230),
    Level.ALERT: (0, 120, 250),
    Level.CRITICAL: (0, 0, 220),
}
WINDOW = "Drowsiness assistant"


def draw_overlay(frame: np.ndarray, status: Status, speed_kmh: float | None) -> None:
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 42), COLORS[status.level], -1)
    ear = "--" if status.ear is None else f"{status.ear:.2f}"
    text = f"{status.level.name}   EAR {ear}   PERCLOS {status.perclos:.0%}"
    cv2.putText(frame, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    if speed_kmh is not None:
        cv2.putText(frame, f"{speed_kmh:.0f} km/h", (w - 130, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(frame, status.reason, (10, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLORS[status.level], 2)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Driver drowsiness assistant")
    p.add_argument("--source", type=int, default=DEFAULT.camera_index, help="camera index")
    p.add_argument("--obd-port", default=None, help="OBD-II serial/Bluetooth port (optional)")
    p.add_argument("--log", default=None, help="write per-frame CSV log to this path")
    p.add_argument("--no-display", action="store_true", help="run without a window")
    p.add_argument("--no-voice", action="store_true", help="disable spoken alerts")
    p.add_argument("--buzzer-pin", type=int, default=None, help="GPIO pin for a buzzer (Raspberry Pi)")
    p.add_argument("--no-beep", action="store_true", help="disable the beep sound (Windows)")
    return p.parse_args(argv)


def build_notifier(args: argparse.Namespace):
    outputs = [Notifier(voice=not args.no_voice)]
    if not args.no_beep:
        outputs.append(BeepNotifier())
    if args.buzzer_pin is not None:
        try:
            outputs.append(GpioBuzzer(GpioPin(args.buzzer_pin)))
            print(f"Buzzer on GPIO {args.buzzer_pin}")
        except Exception as exc:
            print(f"[buzzer] GPIO {args.buzzer_pin} unavailable ({exc}), continuing without it", file=sys.stderr)
    return CompositeNotifier(*outputs)


def _stop_on_sigterm(signum, frame) -> None:
    raise KeyboardInterrupt  # lets systemd stop the service through the normal cleanup path


def run(args: argparse.Namespace) -> int:
    from detection.landmarks import FaceLandmarker  # imported late so --help works without mediapipe

    cap = cv2.VideoCapture(args.source)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT.frame_height)
    if not cap.isOpened():
        print(f"Could not open camera {args.source}", file=sys.stderr)
        return 1

    landmarker = FaceLandmarker()
    monitor = DrowsinessMonitor(DEFAULT)
    alerts = AlertController(build_notifier(args))
    signal.signal(signal.SIGTERM, _stop_on_sigterm)
    speed = SpeedSource(args.obd_port, DEFAULT.speed_poll_interval_s)
    logger = CsvLogger(args.log) if args.log else None

    print("Running. Press q in the video window to quit." if not args.no_display else "Running headless. Ctrl+C to quit.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera frame not available, stopping.", file=sys.stderr)
                break

            t = time.monotonic()
            points = landmarker.detect(frame)
            if points is None:
                ear = mar = None
            else:
                ear = average_ear(points)
                mar = mouth_aspect_ratio(points)

            speed_kmh = speed.read_kmh()
            status = monitor.update(t, ear, mar, speed_kmh)
            alerts.handle(t, status)

            if logger:
                logger.log(t, status, speed_kmh)

            if not args.no_display:
                draw_overlay(frame, status, speed_kmh)
                cv2.imshow(WINDOW, frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        landmarker.close()
        speed.close()
        if logger:
            logger.close()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    sys.exit(run(parse_args()))
