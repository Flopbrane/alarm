# -*- coding: utf-8 -*-
# pylint: disable=C0301
"""Application-wide single-instance lock."""
#########################
# Author: F.Kurokawa
# Description:
#
#########################

from __future__ import annotations

from io import TextIOWrapper
from pathlib import Path
import tempfile
from types import TracebackType
from typing import Optional


try:
    import msvcrt
except ImportError:  # pragma: no cover - non-Windows fallback
    msvcrt = None


class AppLock:
    """Process-wide lock using a lock file."""

    def __init__(self, name: str = "alarm_app.lock") -> None:
        self.lock_path: Path = Path(tempfile.gettempdir()) / name
        self._handle: Optional[TextIOWrapper] = None

    def acquire(self) -> None:
        """Acquire the lock or raise RuntimeError if another instance is active."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle: TextIOWrapper = open(self.lock_path, "a+", encoding="utf-8")
        if msvcrt is not None:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:  # another instance owns the lock
                handle.close()
                raise RuntimeError("alarm is already running") from exc
        self._handle = handle

    def release(self) -> None:
        """Release the lock."""
        if self._handle is not None:
            try:
                if msvcrt is not None:
                    try:
                        msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                self._handle.close()
            finally:
                self._handle = None

    def __enter__(self) -> "AppLock":
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
