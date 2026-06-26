# -*- coding: utf-8 -*-
# pylint: disable=W2301
"""logs.system_monitorへのブリッジ"""
#########################
# Author: F.Kurokawa
# Description:
# 「表示専用ユーティリティ」に固定するのが正解
#########################
# alarm/system_monitor_bridge.py

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol


class AlarmSystemMonitor(Protocol):
    """alarm 側で必要とする最小 SystemMonitor プロトコル。"""
    def tick(self) -> None:
        """tickを呼ぶ。"""
        ...


class _FallbackSystemMonitor:
    """logger_project が無い環境向けの最小 SystemMonitor。"""

    def __init__(self, logger: Any) -> None:
        self.logger = logger

    def tick(self) -> None:
        """何もしない簡易版。"""
        return


if TYPE_CHECKING:
    from logs.system_monitor import SystemMonitor as _ExternalSystemMonitor
else:
    try:
        from logs.system_monitor import SystemMonitor as _ExternalSystemMonitor
    except ModuleNotFoundError:
        _ExternalSystemMonitor = _FallbackSystemMonitor


SystemMonitor = _ExternalSystemMonitor
