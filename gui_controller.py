# -*- coding: utf-8 -*-
"""gui.pyを呼び出すGUIコントローラクラス"""
#########################
# Author: F.Kurokawa
# Description:
# GUIの呼び出しコントローラクラス
#########################
from alarm_manager_temp import AlarmManager
from gui import AlarmGUI


class GUIController:
    """GUI 開始コントローラクラス"""

    def __init__(self, manager: AlarmManager) -> None:
        self.manager: AlarmManager = manager
        self.gui: AlarmGUI = AlarmGUI(controller=self)
        self._started: bool = False  # 起動済みフラグ
        self.manager.add_listener(self.on_manager_updated)

    def start(self) -> None:
        """GUI を開始する"""
        # 🔹 起動時に一度だけ
        self.manager.start_cycle(condition="startup")
        self._started = True

        # GUI 側で Tk mainloop 開始
        self.gui.start_gui()

    def on_timer(self) -> None:
        """タイマーイベントハンドラ（after 用）"""
        # 🔹 通常ループ
        self.manager.start_cycle(condition="loop")
        # GUI 側のタイマーイベントもセットアップ

    def on_manager_updated(self) -> None:
        """AlarmManager の状態が更新されたときのハンドラ"""
        if not self._started:
            return
        # 再描画・ラベル更新など
        self.gui.update_display()
