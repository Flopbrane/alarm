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
from typing import TYPE_CHECKING

from alarm_ui_model import AlarmUI, AlarmUIPatch
from alarm_payloads import AddPayload, UpdatePayload, DeletePayload

if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager


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
