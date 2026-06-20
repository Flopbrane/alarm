# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
#
#########################
# alarm/logger_bridge.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from logs.log_app import get_logger
except ModuleNotFoundError:
    class _FallbackLogger:
        """logs パッケージが無い環境向けの最小 logger。"""

        def debug(self, *args: Any, **kwargs: Any) -> None:
            return

        def info(self, *args: Any, **kwargs: Any) -> None:
            return

        def warning(self, *args: Any, **kwargs: Any) -> None:
            return

        def error(self, *args: Any, **kwargs: Any) -> None:
            return

    def get_logger() -> "_FallbackLogger":
        return _FallbackLogger()

if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger


def get_alarm_logger() -> "AppLogger":
    """alarm_project 用の Logger 取得口。"""
    return get_logger()
