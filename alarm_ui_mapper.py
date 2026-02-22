# -*- coding: utf-8 -*-
"""
UIデータ↔Internal データへの変換
★========================================================================
🔥 重要注意事項 🔥
UI ↔ Internal 変換・受け渡し専用モジュール
【禁止事項】
- AlarmUI ↔ AlarmJson
- AlarmStateUI ↔ AlarmStateJson
上記の変換 mapper を作成してはならない。
【理由】
- UI層とInternal層の分離を厳格に保つため
- JSON層はあくまで保存・通信のための層であり、UI層とは独立しているべきため
★========================================================================
# ★このファイルで許可されている時間取得
# - datetime.now(): UI入力補助のみ
# - AlarmManager.internal_clock(): 使用禁止！
# ※ UI層での現在時刻取得は、あくまで入力補助目的に限る。
"""
#########################
# Author: F.Kurokawa
# Description:
#  UI <-> Internal mapper(チェック済み)
#########################

from dataclasses import fields
from datetime import datetime, time
from typing import Any

from alarm_internal_model import AlarmInternal
from alarm_states_model import AlarmStateInternal
from alarm_ui_model import AlarmStateView, AlarmUI, AlarmUIPatch
from constants import DEFAULT_SOUND


# ==========================================================
# 🔹 ユーティリティ関数
# ==========================================================
def ui_date_time_to_dt(date_str: str, time_str: str) -> datetime:
    """AlarmUI の date, time から datetime を生成"""
    return datetime.fromisoformat(f"{date_str}T{time_str}")


def ui_default_date_time(
    date_str: str | None,
    time_str: str | None,
) -> tuple[str, str]:
    """
    AlarmUI の date, time のデフォルト補完
    NOTE:
    - UI 層専用
    - 内部ロジック・mapper で使用してはならない
    - 入力補助目的のため datetime.now() を使用する
    """
    now: datetime = datetime.now()  # UI 層専用の現在時刻取得なので、問題なし
    return (
        date_str or now.strftime("%Y-%m-%d"),
        time_str or now.strftime("%H:%M"),
    )


def any_to_dt(v: str | None) -> datetime | None:
    """str|datetime|None → datetime|None (安全ラッパー) ※ UI では使用禁止"""
    if not v:
        return None
    return datetime.fromisoformat(v)


def dt_to_any(dt: datetime | None) -> str | None:
    """datetime|None → str|None (安全ラッパー) ※ UI では使用禁止"""
    if not dt:
        return None
    return dt.isoformat()


class UItoInternalMapper:
    """UIモデルからInternalモデルへの変換クラス"""
    # ----------------------------------------------
    # 🔹 AlarmUI -> AlarmInternal マッパー
    # ----------------------------------------------
    @staticmethod
    def ui_to_internal(ui: AlarmUI) -> AlarmInternal:
        """AlarmUI → AlarmInternal"""

        # ---- 日付・時刻の補完（空なら現在時刻） ----
        date_str: str
        time_str: str
        date_str, time_str = ui_default_date_time(ui.date, ui.time)

        return AlarmInternal(
            id=ui.id or "0",  # 仮ID（正式IDは AlarmManager 側）
            name=(ui.name.strip() if ui.name else f"Alarm{ui.id}"),
            datetime_=ui_date_time_to_dt(date_str, time_str),
            repeat=ui.repeat,
            weekday=[int(x) for x in (ui.weekday or [])],
            week_of_month=[int(x) for x in (ui.week_of_month or [])],
            interval_weeks=ui.interval_weeks or 1,  # 0 や None を防ぐ
            interval_days=ui.interval_days,
            base_date_=any_to_dt(getattr(ui, "base_date", None)),
            custom_desc=ui.custom_desc or "",
            enabled=ui.enabled,
            sound=ui.sound or str(DEFAULT_SOUND),
            skip_holiday=ui.skip_holiday,
            duration=ui.duration,
            snooze_minutes=ui.snooze_minutes,
            snooze_limit=getattr(ui, "snooze_limit", 0),
            end_at=any_to_dt(getattr(ui, "end_at", None)),
        )


class InternaltoUIMapper:
    """InternalモデルからUIモデルへの変換クラス"""
    # ----------------------------------------------
    # 🔹 AlarmInternal -> AlarmUI マッパー(CUIで使用予定)
    # ----------------------------------------------
    @staticmethod
    def internal_to_ui(alarm: AlarmInternal) -> AlarmUI:
        """AlarmInternal → AlarmUI"""
        date_str: str = ""
        time_str: str = ""

        dt: datetime | time | None = alarm.datetime_

        if isinstance(dt, datetime):
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        else:
            date_str = alarm.base_date_.strftime("%Y-%m-%d") if alarm.base_date_ else ""
            time_str = dt.strftime("%H:%M") if isinstance(dt, time) else ""


        return AlarmUI(
            id=alarm.id,
            name=alarm.name,
            date=date_str,
            time=time_str,
            repeat=alarm.repeat,
            weekday=list(alarm.weekday),
            week_of_month=list(alarm.week_of_month),
            interval_weeks=alarm.interval_weeks,
            interval_days=alarm.interval_days,
            custom_desc=alarm.custom_desc,
            enabled=alarm.enabled,
            sound=str(alarm.sound),
            skip_holiday=alarm.skip_holiday,
            duration=alarm.duration,
            snooze_minutes=alarm.snooze_minutes,
            snooze_limit=alarm.snooze_limit,
            end_at=dt_to_any(alarm.end_at),
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
            snoozed_until=dt_to_any(state.snoozed_until),
            snooze_count=state.snooze_count,
            triggered=bool(state.triggered),
            triggered_at=dt_to_any(state.triggered_at),
            last_fired_at=dt_to_any(state.last_fired_at),
            next_fire_datetime=dt_to_any(state.next_fire_datetime),
        )

class UIpatchtoInternalMapper:
    """UIモデルのパッチからInternalモデルへの変換クラス"""
    def apply_ui_patch_to_internal(
        self,
        patch: AlarmUIPatch,
        internal: AlarmInternal,
    ) -> AlarmInternal:
        """AlarmUIPatch(変更された場所には値が、変更されていない場所には None が入る) を
        AlarmInternal に適用して更新"""
        patch_dict: dict[str, Any] = vars(patch)

        for f in fields(AlarmUIPatch):
            value: Any = patch_dict[f.name]
            if value is not None:
                setattr(internal, f.name, value)

        return internal


# =========================================================
