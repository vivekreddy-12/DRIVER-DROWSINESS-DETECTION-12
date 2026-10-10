"""Writes one CSV row per processed frame.

Use the log to check thresholds: look at EAR and PERCLOS around real events,
and count WARNING/ALERT rows in alert-free drives to measure false alarms.
"""
from __future__ import annotations

import csv
import os
from typing import TextIO

from detection.state import Status

FIELDS = ["t", "ear", "mar", "perclos", "closed_for_s", "yawns", "speed_kmh", "level", "reason"]


class CsvLogger:
    def __init__(self, path: str) -> None:
        needs_header = not os.path.exists(path) or os.path.getsize(path) == 0
        self._file: TextIO = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, fieldnames=FIELDS)
        if needs_header:
            self._writer.writeheader()

    def log(self, t: float, status: Status, speed_kmh: float | None) -> None:
        self._writer.writerow({
            "t": f"{t:.3f}",
            "ear": "" if status.ear is None else f"{status.ear:.4f}",
            "mar": "" if status.mar is None else f"{status.mar:.4f}",
            "perclos": f"{status.perclos:.4f}",
            "closed_for_s": f"{status.closed_for_s:.2f}",
            "yawns": status.yawns,
            "speed_kmh": "" if speed_kmh is None else f"{speed_kmh:.1f}",
            "level": status.level.name,
            "reason": status.reason,
        })
        self._file.flush()

    def close(self) -> None:
        self._file.close()
