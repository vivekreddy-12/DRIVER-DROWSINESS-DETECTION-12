"""Vehicle speed from an OBD-II adapter (for example an ELM327 over USB or Bluetooth).

Speed is optional. If no port is given, or the adapter cannot be reached, read_kmh()
returns None and the assistant runs without speed-based escalation.
"""
from __future__ import annotations

import sys
import time

from config import DEFAULT


class SpeedSource:
    def __init__(self, port: str | None = None, poll_interval_s: float = DEFAULT.speed_poll_interval_s) -> None:
        self._conn = None
        self._obd = None
        self._poll_interval = poll_interval_s
        self._last_read = float("-inf")
        self._last_value: float | None = None
        if port is None:
            return
        try:
            import obd
            self._obd = obd
            self._conn = obd.OBD(port, fast=False)
            if not self._conn.is_connected():
                print(f"[obd] no response on {port}, speed disabled", file=sys.stderr)
                self._conn = None
        except Exception as exc:
            print(f"[obd] could not connect ({exc}), speed disabled", file=sys.stderr)
            self._conn = None

    @property
    def available(self) -> bool:
        return self._conn is not None

    def read_kmh(self) -> float | None:
        """Latest speed in km/h. Queries the adapter at most once per poll interval."""
        if self._conn is None:
            return None
        now = time.monotonic()
        if now - self._last_read < self._poll_interval:
            return self._last_value
        self._last_read = now
        try:
            response = self._conn.query(self._obd.commands.SPEED)
            self._last_value = None if response.is_null() else float(response.value.magnitude)
        except Exception:
            self._last_value = None
        return self._last_value

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
