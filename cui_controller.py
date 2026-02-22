# -*- coding: utf-8 -*-
"""cui.pyを呼び出すCUIコントローラクラス"""
#########################
# Author: F.Kurokawa
# Description:
# CUIの呼び出しコントローラクラス
#########################

import time

from alarm_manager_temp import AlarmManager

class CUIController:
    """CUI 開始コントローラクラス"""

    def __init__(self, manager: AlarmManager) -> None:
        self.manager: AlarmManager = manager
        self._stop = False
        self._started = False  # ← 起動済みフラグ

    def run(self) -> None:
        """CUI メインループを開始する"""
        self._stop = False

        # 🔹 起動時に一度だけ
        self.manager.start_cycle(condition="startup")
        self._started = True

        while not self._stop:
            sleep_seconds: float = self.manager.get_sleep_seconds()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            self.manager.start_cycle(condition="loop")

    def stop(self) -> None:
        """CUI メインループを停止する"""
        self._stop = True

    def on_timer(self) -> None:
        """1 tick 分の処理"""
        # 🔹 通常ループ
        self.manager.start_cycle(condition="loop")
