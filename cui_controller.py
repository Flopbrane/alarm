# -*- coding: utf-8 -*-
"""cui.pyを呼び出すCUIコントローラクラス"""
#########################
# Author: F.Kurokawa
# Description:
# CUIの呼び出しコントローラクラス
#########################
from __future__ import annotations
import time
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager

class CUIController:
    """CUI 開始コントローラクラス"""

    def __init__(self, manager: "AlarmManager") -> None:
        self.manager: "AlarmManager" = manager
        self._stop = False
        self._started = False  # ← 起動済みフラグ

    def run(self) -> None:
        """CUI メインループを開始する"""
        self._stop = False

        self.manager.start_cycle(condition="startup")
        self._started = True

        while not self._stop:
            # 🔹 ここ追加🔥
            if self._check_user_input():
                continue

            sleep_seconds: float = self.manager.get_sleep_seconds()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

            self.manager.start_cycle(condition="loop")

    def _check_user_input(self) -> bool:
        """ユーザー入力をチェックして、終了コマンドがあれば停止する"""
        import msvcrt  # Windows専用

        if msvcrt.kbhit():
            key = msvcrt.getch()

            if key == b"q":
                print("終了します")
                self.stop()
                return True

        return False

    def stop(self) -> None:
        """CUI メインループを停止する"""
        self._stop = True

    def on_timer(self) -> None:
        """1 tick 分の処理"""
        # 🔹 通常ループ
        self.manager.start_cycle(condition="loop")
