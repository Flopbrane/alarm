# -*- coding: utf-8 -*-
"""gui.pyを呼び出すGUIコントローラクラス"""
#########################
# Author: F.Kurokawa
# Description:
# GUIの呼び出しコントローラクラス
#########################
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager
    from gui import AlarmGUI


class GUIController:
    """GUI 開始コントローラクラス"""
    def __init__(self, manager: "AlarmManager") -> None:
        self.manager: "AlarmManager" = manager
        self._started = False
        self.gui: "AlarmGUI | None" = None
        self.manager.add_listener(self.on_manager_updated)

    def start(self) -> None:
        """GUI を開始する"""
        # 循環参照回避のため、ここでインポート
        from gui import AlarmGUI

        self.gui = AlarmGUI(controller=self)

        self.manager.start_cycle(condition="startup")
        self._started = True

        self.gui.start_gui()

    def on_manager_updated(self) -> None:
        """AlarmManager の状態が更新されたときのハンドラ"""
        if not self._started or self.gui is None:
            return

        # self.gui.load_alarms()
