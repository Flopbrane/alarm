# -*- coding: utf-8 -*-
# pylint: disable=C0415
"""gui.pyを呼び出すGUIコントローラクラス"""
#########################
# Author: F.Kurokawa
# Description:
# GUIの呼び出しコントローラクラス
#########################
from __future__ import annotations
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from alarm.alarm_internal_model import AlarmInternal
from alarm.alarm_manager_temp import NextAlarmInfo
from alarm.alarm_states_model import AlarmStateInternal
from alarm.alarm_ui_model import AlarmUI, AlarmUIPatch
from alarm.data_ui_to_mgr_adapter import DataEditAdapter

if TYPE_CHECKING:
    from alarm.alarm_manager import AlarmManager
    from alarm.gui import AlarmGUI


class GUIController:
    """GUI 開始コントローラクラス"""
    def __init__(self, manager: "AlarmManager") -> None:
        self.manager: "AlarmManager" = manager
        self.data_adapter = DataEditAdapter(manager)
        self._started = False
        self.gui: "AlarmGUI | None" = None
        self.manager.add_listener(self.on_manager_updated)
        self.data_ui_to_mgr_adapter: DataEditAdapter = self.data_adapter  # type: ignore[assignment]

    def start(self) -> None:
        """GUI を開始する"""
        # 循環参照回避のため、ここでインポート
        from alarm.gui import AlarmGUI

        self.gui = AlarmGUI(controller=self)  # type: ignore[arg-type]

        # self.manager.start_cycle(condition="startup")
        self._started = True

        self.gui.start_gui()

    def on_manager_updated(self) -> None:
        """AlarmManager の状態が更新されたときのハンドラ"""
        if not self._started or self.gui is None:
            return

        # self.gui.load_alarms()

    def get_alarm_file_path(self) -> Path:
        """GUI 側へ alarms.json の場所だけを渡す。"""
        return self.manager.alarm_file_path

    def reload_after_external_json_edit(self) -> None:
        """外部 JSON 編集後に Manager の公開サイクルで再読込する。"""
        self.manager.start_cycle(condition="startup")

    def run_alarm_cycle(self) -> None:
        """GUI の定期監視から Manager の通常サイクルを回す。"""
        self.manager.start_cycle(condition="loop")

    def get_active_alarm_ui(self) -> AlarmUI | None:
        """鳴動中またはスヌーズ中のアラームを UI モデルで返す。"""
        state: AlarmStateInternal | None = self.manager.get_active_alarm_state()
        if state is None:
            return None
        return self.get_alarm_ui_by_id(state.id)

    def is_alarm_triggered(self, alarm_id: str) -> bool:
        """指定アラームが鳴動中か。"""
        state: AlarmStateInternal | None = self.manager.get_state_by_id(alarm_id)
        return bool(state and state.triggered)

    def get_snoozed_until(self, alarm_id: str) -> datetime | None:
        """指定アラームのスヌーズ解除時刻を返す。"""
        state: AlarmStateInternal | None = self.manager.get_state_by_id(alarm_id)
        if state is None:
            return None
        return state.snoozed_until

    def get_next_alarm_ui(self) -> tuple[datetime, AlarmUI] | None:
        """次回鳴動予定の先頭1件を UI モデルへ変換して返す。"""
        next_alarms: list[NextAlarmInfo] = self.manager.get_next_alarms(1)
        if not next_alarms:
            return None

        item: NextAlarmInfo = next_alarms[0]
        return item["next_datetime"], self.manager.internal_to_ui_mapper.internal_to_ui(
            item["alarm"]
        )

    def get_all_alarm_uis(self) -> list[AlarmUI]:
        """一覧表示用に全アラームを UI モデルへ変換して返す。"""
        alarms: list[AlarmUI] = []
        for alarm in self.manager.alarms:
            ui_alarm: AlarmUI = self.manager.internal_to_ui_mapper.internal_to_ui(alarm)
            alarms.append(ui_alarm)
        return alarms

    def add_alarm_from_ui(self, ui_alarm: AlarmUI) -> None:
        """GUI からの新規追加を Manager の公開入口へ流す。"""
        self.data_adapter.add_alarm(ui_alarm)

    def update_alarm_from_ui(self, alarm_id: str, patch: AlarmUIPatch) -> None:
        """GUI からの編集差分を Manager の公開入口へ流す。"""
        self.data_adapter.update_alarm(alarm_id, patch)

    def get_alarm_ui_by_id(self, alarm_id: str) -> AlarmUI | None:
        """編集用に Internal を UI モデルへ戻して返す。"""
        alarm: AlarmInternal | None = self.manager.get_alarm_by_id(alarm_id)
        if alarm is None:
            return None
        return self.manager.internal_to_ui_mapper.internal_to_ui(alarm)

    def get_snooze_default_minutes(self) -> int:
        """GUI 表示用の既定スヌーズ分数。"""
        return self.manager.snooze_default

    def stop_alarm_from_ui(self) -> bool:
        """鳴動中またはスヌーズ中のアラーム停止要求。"""
        state: AlarmStateInternal | None = self.manager.get_active_alarm_state()
        if state is None:
            return False

        self.manager.stop_alarm(state)
        return True

    def snooze_alarm_from_ui(
        self,
        minutes: int,
    ) -> tuple[bool, str, datetime | None]:
        """鳴動中アラームに対してスヌーズ要求を出す。"""
        state: AlarmStateInternal | None = self.manager.get_active_alarm_state()
        if state is None or not state.triggered:
            return False, "", None

        alarm: AlarmInternal | None = self.manager.get_alarm_by_id(state.id)
        if alarm is None:
            return False, "", None

        triggered_at: datetime | None = state.triggered_at
        if (
            isinstance(triggered_at, datetime)
            and (datetime.now() - triggered_at).total_seconds() > alarm.duration + 5
        ):
            return False, alarm.name, None

        self.manager.player.stop()
        self.manager.snooze_alarm(alarm, state, minutes)
        self.manager.request_stop()

        next_time: datetime | None = state.snoozed_until
        return True, alarm.name, next_time

    def delete_alarm_from_ui(self, alarm_id: str) -> None:
        """GUI から指定されたアラームIDを削除する。"""
        self.delete_alarms_from_ui([alarm_id])

    def delete_alarms_from_ui(self, alarm_ids: list[str]) -> None:
        """GUI から指定されたアラームID群を削除する。"""
        normalized_alarm_ids: list[str] = []
        for alarm_id in alarm_ids:
            alarm: AlarmUI | None = self.get_alarm_ui_by_id(alarm_id)
            if alarm is None or alarm.id is None:
                continue
            normalized_alarm_ids.append(str(alarm.id))

        if not normalized_alarm_ids:
            return

        self.data_adapter.delete_alarms(normalized_alarm_ids)

    def remove_gui_listener(self, listener: Callable[[], None]) -> None:
        """GUI の listener 解除を Manager の公開窓口側で仲介する。"""
        self.manager.remove_listener(listener)
