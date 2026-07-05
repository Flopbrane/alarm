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
from __future__ import annotations
from datetime import datetime, time, date
from dataclasses import fields
from typing import Any

from alarm.alarm_internal_model import AlarmInternal
from alarm.alarm_states_model import AlarmStateInternal
from alarm.alarm_ui_model import AlarmUI, AlarmUIPatch, AlarmDisplayRow, AlarmStateView
from alarm.weekday_formatter import weekday_to_str
from alarm.constants import DEFAULT_SOUND


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


def any_to_dt(v: str | datetime | None) -> datetime | None:
    """str|datetime|None → datetime|None (安全ラッパー) ※ UI では使用禁止"""
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(v)


def dt_to_any(dt: datetime | str | None) -> str | None:
    """datetime|None → str|None (安全ラッパー) ※ UI では使用禁止"""
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
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

        dt: datetime | None = alarm.datetime_

        if dt is None:
            date_str = ""
            time_str = ""
        else:
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")


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


class InternaltoView:
    """InternalモデルからViewモデルへの変換クラス"""
    # ----------------------------------------------
    # 🔹 AlarmStateInternal -> AlarmStateView マッパー
    # ----------------------------------------------
    @staticmethod
    def stateinternal_to_view(state: AlarmStateInternal) -> AlarmStateView:
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
        """AlarmUIPatch → AlarmInternal"""
        patch_dict: dict[str, Any] = vars(patch)

        # =========================================
        # 🔹 datetime_ の更新（最優先）
        # =========================================
        date_str: Any | None = patch_dict.get("date")
        time_str: Any | None = patch_dict.get("time")

        if (date_str is not None or time_str is not None) and internal.datetime_ is not None:
            # 既存値を取得
            current_dt: datetime = internal.datetime_

            # date補完
            if date_str is not None:
                new_date: date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                new_date = current_dt.date()

            # time補完
            if time_str is not None:
                new_time: time = datetime.strptime(time_str, "%H:%M").time()
            else:
                new_time = current_dt.time()

            # 合成
            internal.datetime_ = datetime.combine(new_date, new_time)
        # =========================================
        # 🔹 その他フィールド
        # =========================================
        for f in fields(AlarmUIPatch):
            value: Any = patch_dict[f.name]

            if value is None:
                continue

            # datetime系と識別子はここで触らない
            if f.name in ("id", "date", "time"):
                continue

            # base_dateはスキップ
            if f.name == "base_date":
                continue

            if f.name == "end_at":
                internal.end_at = any_to_dt(value)
                continue

            setattr(internal, f.name, value)

        return internal


class InternalToViewMapper:
    """Internalモデルから表示用の行データへの変換クラス"""

    @staticmethod
    def _wrap_custom_desc(text: str, width: int = 24) -> str:
        """custom_desc を見やすい長さで改行する。"""
        if len(text) <= width:
            return text

        lines: list[str] = []
        for index in range(0, len(text), width):
            lines.append(text[index : index + width])
        return "\n".join(lines)

    @staticmethod
    def _format_custom_desc(alarm: AlarmInternal) -> str:
        """custom 設定の中身を一覧向けに簡潔に文字列化する。"""
        if (alarm.repeat or "") != "custom":
            return InternalToViewMapper._wrap_custom_desc(alarm.custom_desc or "")

        def _format_week_item(value: int) -> str:
            if value == 6:
                return "最終週"
            return f"第{value}週"

        parts: list[str] = []
        if alarm.interval_weeks and alarm.interval_weeks != 1:
            parts.append(f"{alarm.interval_weeks}週おき")
        if alarm.weekday:
            parts.append(f"曜:{weekday_to_str(list(alarm.weekday))}")
        if alarm.week_of_month:
            parts.append(f"週:{','.join(_format_week_item(v) for v in alarm.week_of_month)}")
        if alarm.interval_days:
            parts.append(f"{alarm.interval_days}日おき")

        desc: str = " / ".join(parts) if parts else "カスタム"
        return InternalToViewMapper._wrap_custom_desc(desc)

    @staticmethod
    def internal_to_display_row(
        row_no: int,
        alarm: AlarmInternal,
        state: AlarmStateInternal | None = None,
    ) -> AlarmDisplayRow:
        """AlarmInternal → AlarmDisplayRow"""
        # AlarmInternal は AlarmManager 通過後に必ず UUID が補完される。
        # DisplayRow は Manager 管理下の既存アラームだけを対象にするため、
        # ここでは alarm.id を str として扱う。
        alarm_id: str = alarm.id

        dt: datetime | None = alarm.datetime_

        date_str: str = dt.strftime("%Y-%m-%d") if dt else ""
        time_str: str = dt.strftime("%H:%M") if dt else ""

        weekday_str: str = weekday_to_str(list(alarm.weekday)) if alarm.weekday else ""

        next_alarm_datetime: datetime | None = (
            state.next_fire_datetime if state else None
        )

        return AlarmDisplayRow(
            row_no=row_no,  # UIに表示されるナンバー
            alarm_id=alarm_id,  # 本来のアラームUUID。表示用には使用しない内部値
            name=alarm.name or "(名称なし)",
            date=date_str,
            time=time_str,
            repeat=alarm.repeat or "single",
            weekday=weekday_str,
            enabled=bool(alarm.enabled),
            next_alarm_datetime=next_alarm_datetime,
            skip_holiday=bool(alarm.skip_holiday),
            duration=int(alarm.duration),
            snooze_minutes=int(alarm.snooze_minutes),
            end_at=alarm.end_at.date().isoformat() if alarm.end_at else "",
            snooze_limit=int(alarm.snooze_limit),
            custom_desc=InternalToViewMapper._format_custom_desc(alarm),
        )


# =========================================================
