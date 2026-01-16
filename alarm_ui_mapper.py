# -*- coding: utf-8 -*-
"""
UIデータ↔Internal データへの変換
"""
#########################
# Author: F.Kurokawa
# Description:
#  UI <-> Internal mapper
#########################

from datetime import datetime

from alarm_internal_model import AlarmInternal, AlarmStateInternal
from alarm_ui_model import AlarmStateView, AlarmUI
from constants import DEFAULT_SOUND


class UItoInternalMapper:
    """UIモデルからInternalモデルへの変換クラス"""
    # ----------------------------------------------
    # 🔹 AlarmUI -> AlarmInternal マッパー
    # ----------------------------------------------
    @staticmethod
    def ui_to_internal(ui: AlarmUI) -> AlarmInternal:
        """AlarmUI → AlarmInternal"""

        # ---- 日付・時刻の補完（空なら現在時刻） ----
        date: str = ui.date or datetime.now().strftime("%Y-%m-%d")
        time: str = ui.time or datetime.now().strftime("%H:%M")

        return AlarmInternal(
            id=ui.id or 0,  # 仮ID（正式IDは AlarmManager 側）
            name=(ui.name.strip() if ui.name else f"Alarm{ui.id}"),
            datetime_=datetime.fromisoformat(f"{date}T{time}"),
            repeat=ui.repeat,
            weekday=[int(x) for x in (ui.weekday or [])],
            week_of_month=[int(x) for x in (ui.week_of_month or [])],
            interval_weeks=ui.interval_weeks or 1,  # 0 や None を防ぐ
            custom_desc=ui.custom_desc or "",
            enabled=ui.enabled,
            sound=ui.sound or str(DEFAULT_SOUND),
            skip_holiday=ui.skip_holiday,
            duration=ui.duration,
            snooze_minutes=ui.snooze_minutes,
            snooze_limit=getattr(ui, "snooze_limit", 0),
        )


class InternaltoUIMapper:
    """InternalモデルからUIモデルへの変換クラス"""
    # ----------------------------------------------
    # 🔹 AlarmInternal -> AlarmUI マッパー(CUIで使用予定)
    # ----------------------------------------------
    @staticmethod
    def internal_to_ui(alarm: AlarmInternal) -> AlarmUI:
        """AlarmInternal → AlarmUI"""
        date_str: str = alarm.datetime_.date().strftime("%Y-%m-%d")
        time_str: str = alarm.datetime_.time().strftime("%H:%M")

        return AlarmUI(
            id=alarm.id,
            name=alarm.name,
            date=date_str,
            time=time_str,
            repeat=alarm.repeat,
            weekday=list(alarm.weekday),
            week_of_month=list(alarm.week_of_month),
            interval_weeks=alarm.interval_weeks,
            custom_desc=alarm.custom_desc,
            enabled=alarm.enabled,
            sound=str(alarm.sound),
            skip_holiday=alarm.skip_holiday,
            duration=alarm.duration,
            snooze_minutes=alarm.snooze_minutes,
        )


class InternaltoViewMapper:
    """InternalモデルからViewモデルへの変換クラス"""
    # ----------------------------------------------
    # 🔹 AlarmStateInternal -> AlarmStateView マッパー
    # ----------------------------------------------
    @staticmethod
    def stateinternal_to_stateview(state: AlarmStateInternal) -> AlarmStateView:
        """AlarmStateInternal → AlarmStateView"""
        return AlarmStateView(
            id=state.id,
            snoozed_until=(
                state.snoozed_until.isoformat(sep=" ") if state.snoozed_until else None
            ),
            snooze_count=state.snooze_count,
            triggered=bool(state.triggered),
            triggered_at=(
                state.triggered_at.isoformat(sep=" ") if state.triggered_at else None
            ),
            last_fired_at=(
                state.last_fired_at.isoformat(sep=" ") if state.last_fired_at else None
            ),
        )
