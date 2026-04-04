# -*- coding: utf-8 -*-
"""systemの監視を行うモジュール"""
#########################
# Author: F.Kurokawa
# Description:
# system_monitor
#########################
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger

class SystemMonitor:
    """システムの監視を行うクラス"""
    def __init__(self, logger: "AppLogger") -> None:

        self.logger: "AppLogger" = logger
        self._last_tick: datetime | None = None
        self._boot_time: float = psutil.boot_time()

    def tick(self) -> None:
        """1 tick 分の処理"""
        now: datetime = datetime.now()

        # clock jump
        if self._last_tick:
            diff: float = (now - self._last_tick).total_seconds()
            if diff > 120:
                self.logger.warning("clock_jump_detected", context={"diff": diff})

        self._last_tick = now
        if self._boot_time != psutil.boot_time(): # → 再起動確定
            self.logger.warning("system_reboot_detected")
            self._boot_time = psutil.boot_time()

        # uptime
        uptime: float = now.timestamp() - self._boot_time
        if int(uptime) % 600 == 0:
            self.logger.info("system_uptime", context={"uptime": uptime})
        # CPU使用率
        cpu_percent: float = psutil.cpu_percent(interval=None)
        self.logger.info("system_cpu_percent", context={"cpu_percent": cpu_percent})
