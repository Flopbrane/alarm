# -*- coding: utf-8 -*-
"""各UIのコントロール、及び、データ編集ラッパーモジュール
[Manager Cycle]
start_cycle
    -> UIController.start()
    -> UIControllerからDataEditAdapterを呼び出す
"""
#########################
# Author: F.Kurokawa
# Description:
#  - 各UIのコントロール、及び、データ編集ラッパーモジュール
#########################
from __future__ import annotations
import time as time_module
from typing import TYPE_CHECKING

from alarm_ui_model import AlarmUI, AlarmUIPatch
from alarm_payloads import AddPayload, UpdatePayload, DeletePayload

if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager


class CUIController:
    """CUI 開始コントローラクラス"""

    def __init__(self, manager: "AlarmManager") -> None:
        self.manager: "AlarmManager" = manager
        self._stop: bool = False
        self._started: bool = False  # ← 起動済みフラグ

    def run(self) -> None:
        """CUI メインループを開始する"""
        print("🔥 CUI run 開始")
        self._stop = False

        # 🔹 起動時に一度だけ
        self.manager.start_cycle(condition="startup")
        self._started = True

        while not self._stop:
            print("🔁 ループ中")
            sleep_seconds: float = self.manager.get_sleep_seconds()
            print(f"⏱ 次のループまで {sleep_seconds:.2f} 秒")
            if sleep_seconds > 0:
                time_module.sleep(sleep_seconds)
            self.manager.start_cycle(condition="loop")

    def stop(self) -> None:
        """CUI メインループを停止する(アラーム駆動停止)"""
        self._stop = True

    def on_timer(self) -> None:
        """1 tick 分の処理"""
        # 🔹 通常ループ
        self.manager.start_cycle(condition="loop")


class GUIController:
    """GUI 開始コントローラクラス"""
    def __init__(self, manager: "AlarmManager") -> None:
        self.manager: "AlarmManager" = manager
        self.gui = None  # GUI クラスは後でインポートしてセットする
        self._started: bool = False  # 起動済みフラグ
        self.manager.add_listener(self.on_manager_updated)

    def start(self) -> None:
        """GUI を開始する"""
         # 循環参照回避のため、ここでインポート
        from gui import AlarmGUI
        self.gui: AlarmGUI = AlarmGUI(controller=self)
        # 🔹 起動時に一度だけ
        self.manager.start_cycle(condition="startup")
        self._started = True

        # GUI 側で Tk mainloop 開始
        self.gui.start_gui()

    def on_timer(self) -> None:
        """タイマーイベントハンドラ（after 用）"""
        # 🔹 通常ループ
        self.manager.start_cycle(condition="loop")
        self.gui.root.after(1000, self.on_timer)
        # GUI 側のタイマーイベントもセットアップ

    def on_manager_updated(self) -> None:
        """AlarmManager の状態が更新されたときのハンドラ"""
        if not self._started:
            return

        # gui.pyが未完成のため
        # 再描画・ラベル更新など
        #self.gui.load_alarms()


class DataEditAdapter:
    """UIからAlarmManagerへのデータ編集をラップするクラス"""
    def __init__(self, manager: "AlarmManager") -> None:
        self.manager: "AlarmManager" = manager

    def add_alarm(self, ui_alarm: AlarmUI) -> None:
        """アラームを追加する"""
        if not ui_alarm.name:
            raise ValueError("アラーム名が空です")

        payload = AddPayload(ui_alarm=ui_alarm)

        self.manager.apply_alarm_mutation("add", payload)


    def update_alarm(self, alarm_id: str, patch: AlarmUIPatch) -> None:
        """アラームを更新する"""
        payload = UpdatePayload(alarm_id=alarm_id, patch=patch)

        self.manager.apply_alarm_mutation("update", payload)


    def delete_alarms(self, alarm_id_list: list[str]) -> None:
        """アラームを削除する"""
        payload = DeletePayload(alarm_id_list=alarm_id_list)

        self.manager.apply_alarm_mutation("delete", payload)
