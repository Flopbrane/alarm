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

        self._check_clock_jump(now)
        self._check_reboot(now)
        self._log_uptime(now)
        self._log_cpu()

        self._last_tick = now

    def _check_clock_jump(self, now: datetime) -> None:
        """時計のジャンプを検出する（前回のtickから120秒以上経過していたら）"""
        if not self._last_tick:
            return

        diff: float = (now - self._last_tick).total_seconds()
        if diff > 120:
            self.logger.warning(
                "clock_jump_detected",
                context={"diff": diff},
            )
        self._last_tick = now


    def _check_reboot(self, now: datetime) -> bool:
        """システムの再起動を検出する（boot_timeが変わったら）"""
        current_boot: float = psutil.boot_time()
        reboot_detected: bool = self._boot_time != current_boot

        if reboot_detected:
            self.logger.warning(
                "system_reboot_detected",
                context={
                    "category": "system",
                    "status": "reboot",
                    "previous_boot_time": self._boot_time,
                    "current_boot_time": current_boot,
                    "detected_at": now.isoformat(),
                },
            )
            self._boot_time = current_boot

        return reboot_detected


    def _log_uptime(self, now: datetime) -> None:
        """システムの稼働時間をログに記録する（10分ごと）"""
        uptime: float = now.timestamp() - self._boot_time

        if int(uptime) % 600 == 0:
            self.logger.info(
                "system_uptime",
                context={"uptime": uptime},
            )

    def _log_cpu(self) -> None:
        """CPU使用率をログに記録する"""
        cpu_percent: float = psutil.cpu_percent(interval=None)

        self.logger.info(
            "system_cpu_percent",
            context={"cpu_percent": cpu_percent},
        )
