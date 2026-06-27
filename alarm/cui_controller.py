# -*- coding: utf-8 -*-
# pylint: disable=C0415
"""cui.pyを呼び出すCUIコントローラクラス"""
#########################
# Author: F.Kurokawa
# Description:
# CUIの呼び出しコントローラクラス
#########################
from __future__ import annotations
import time
from datetime import datetime
from typing import TYPE_CHECKING

from alarm.alarm_internal_model import AlarmInternal
from alarm.alarm_states_model import AlarmStateInternal
from alarm.alarm_ui_mapper import InternalToViewMapper
from alarm.alarm_ui_model import AlarmDisplayRow, AlarmUI, AlarmUIPatch
from alarm.data_ui_to_mgr_adapter import DataEditAdapter


if TYPE_CHECKING:
    from alarm.alarm_manager import AlarmManager

class CUIController:
    """CUI 開始コントローラクラス"""

    def __init__(self, manager: "AlarmManager") -> None:
        self.manager: "AlarmManager" = manager
        self.data_adapter = DataEditAdapter(manager)
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
            key: bytes = msvcrt.getch()

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

    def refresh_for_display(self) -> None:
        """表示前に Manager の公開サイクルを1回進める。"""
        self.manager.start_cycle(condition="loop")

    def get_alarm_display_rows(self) -> list[AlarmDisplayRow]:
        """CUI 一覧表示用の行データを返す。"""
        valid_alarms: list[AlarmInternal] = [
            alarm for alarm in self.manager.alarms if alarm.id
        ]

        def get_sort_key(alarm: AlarmInternal) -> datetime:
            state: AlarmStateInternal | None = self.manager.get_state_by_id(alarm.id)
            if state is not None and state.next_fire_datetime is not None:
                return state.next_fire_datetime
            return datetime.max

        sorted_alarms: list[AlarmInternal] = sorted(
            valid_alarms,
            key=get_sort_key,
        )

        rows: list[AlarmDisplayRow] = []
        for row_no, alarm in enumerate(sorted_alarms, start=1):
            state: AlarmStateInternal | None = self.manager.get_state_by_id(alarm.id)
            rows.append(
                InternalToViewMapper.internal_to_display_row(
                    row_no=row_no,
                    alarm=alarm,
                    state=state,
                )
            )
        return rows

    def add_alarm_from_ui(self, ui_alarm: AlarmUI) -> None:
        """CUI からの追加を Manager の公開入口へ流す。"""
        self.data_adapter.add_alarm(ui_alarm)

    def get_alarm_id_by_row_no(self, row_no: int) -> str | None:
        """表示用 row_no から内部 alarm_id を引く。"""
        for row in self.get_alarm_display_rows():
            if row.row_no == row_no:
                return row.alarm_id
        return None

    def delete_alarm_by_row_no(self, row_no: int) -> bool:
        """表示番号で指定されたアラームを削除する。"""
        alarm_id = self.get_alarm_id_by_row_no(row_no)
        if not alarm_id:
            return False
        self.data_adapter.delete_alarms([alarm_id])
        return True

    def toggle_alarm_enabled_by_row_no(self, row_no: int) -> bool:
        """表示番号で指定されたアラームの有効/無効を切り替える。"""
        alarm_id: str | None = self.get_alarm_id_by_row_no(row_no)
        if not alarm_id:
            return False

        alarm: AlarmInternal | None = self.manager.get_alarm_by_id(alarm_id)
        if alarm is None:
            return False

        self.data_adapter.update_alarm(
            alarm_id,
            AlarmUIPatch(enabled=not alarm.enabled),
        )
        return True
