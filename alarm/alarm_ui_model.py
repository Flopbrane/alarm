# -*- coding: utf-8 -*-
"""
"id",              # 行識別子（必ず先頭）
"name",            # 表示名
"date",            # YYYY-MM-DD
"time",            # HH:MM
"repeat",          # none / daily / weekly / custom ...
"weekday",         # [0,1,4] など
"week_of_month",   # [1,3] など
"interval_weeks",  # weekly_x の x
"interval_days",   # days_span の x
"base_date",       # custom の基準日
"custom_desc",     # カスタム説明文

"enabled",         # ON/OFF
"sound",           # WAV ファイル
"skip_holiday",    # True/False

"duration",        # 再生秒数
"snooze_minutes",  # 初スヌーズ分
"snooze_limit",    # 回数上限
"""
#########################
# Author: F.Kurokawa
# Description:
# 　UI dataclass(UIモデル → 人間との境界)
#########################
# 標準ライブラリ
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Union, cast

# 自作モジュール
from alarm.constants import (
    DEFAULT_SOUND,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_SNOOZE_MINUTES,
    DEFAULT_SNOOZE_LIMIT,
)

@dataclass
class AlarmUI:
    """新規作成用 UI dataclass
    id -> UUID に変更(str にする)"""
    # 行識別子（必ず先頭）
    # {新規作成用なら Noneでも構わない。
    # UUID決定権はmanager側にある}
    id: Optional[str] = None
    name: str = ""  # 表示名
    date: str = ""  # YYYY-MM-DD
    time: str = ""  # HH:MM
    repeat: str = "single"  # single / daily / weekly / custom ...
    weekday: List[Union[int, str]] = field(
        default_factory=lambda: cast(List[Union[int, str]], [])
    )  # [0,1,4] など
    # UI入力専用（int/str混在可）
    # Mapper で list[int] に正規化される
    week_of_month: List[int] = field(
        default_factory=lambda: cast(List[int], [])
    )  # [1,3] など
    interval_weeks: int = 1  # weekly_x の x
    interval_days: int|None = None  # days_span の x
    base_date: str | None = None  # custom の基準日
    custom_desc: str = ""  # カスタム説明文

    enabled: bool = True  # ON/OFF
    sound: str = str(DEFAULT_SOUND)  # WAV ファイル
    skip_holiday: bool = False  # True/False

    duration: int = DEFAULT_DURATION_SECONDS  # 再生秒数
    snooze_minutes: int = DEFAULT_SNOOZE_MINUTES  # 初スヌーズ分
    snooze_limit: int = DEFAULT_SNOOZE_LIMIT  # 回数上限
    end_at: str | None = None  # アラームの終了日時（UI/Storage境界は文字列）


@dataclass
class AlarmUIPatch:
    """編集用（差分）UI dataclass"""

    id: str = ""  # 行識別子（必ず先頭）
    name: Optional[str] = None  # 表示名
    date: Optional[str] = None  # YYYY-MM-DD
    time: Optional[str] = None  # HH:MM
    repeat: Optional[str] = None  # single / daily / weekly / custom ...

    weekday: Optional[List[Union[int, str]]] = None  # [0,1,4] など
    # UI入力専用（int/str混在可）
    # Mapper で list[int] に正規化される
    week_of_month: Optional[List[int]] = None  # [1,3] など

    interval_weeks: Optional[int] = None  # weekly_x の x
    interval_days: Optional[int] = None  # days_span の x
    # base_date: Optional[str] = None  # custom の基準日
    custom_desc: Optional[str] = None  # カスタム説明文

    enabled: Optional[bool] = None  # ON/OFF
    sound: Optional[str] = None  # WAV ファイル
    skip_holiday: Optional[bool] = None  # True/False

    duration: Optional[int] = None  # 再生秒数
    snooze_minutes: Optional[int] = None  # 初スヌーズ分
    snooze_limit: Optional[int] = None  # 回数上限
    end_at: Optional[str | None] = None  # アラームの終了日時（UI/Storage境界は文字列）


@dataclass(frozen=True)
class AlarmStateView:
    """将来的に 状態表示専用の画面 / CUI表示 / Viewer表示 を作る場合に備えて、状態表示専用の dataclass を作っておく"""
    id: Optional[str] = None  # 行識別子（必ず先頭）
    snoozed_until: Optional[str] = None  # ISO文字列
    snooze_count: int = 0 # スヌーズ回数
    triggered: bool = False # 鳴動中か？
    triggered_at: Optional[str] = None  # 鳴動開始時刻
    last_fired_at: Optional[str] = None  # 最終鳴動時刻
    next_fire_datetime: Optional[str] = None  # 次回鳴動予定日


@dataclass(frozen=True)
class AlarmListItem:
    """CUI表示用のアラームリストアイテム"""
    alarm_id: str
    alarm_ui: AlarmUI
    next_datetime: datetime | None


@dataclass(frozen=True)
class AlarmDisplayRow:
    """GUI / CUI / Viewer 共通のアラーム表示行データ。"""
    row_no: int #UIに表示されるナンバー
    alarm_id: str # 本来のアラームUUID(表示用には使用しない内部値)
    name: str
    date: str
    time: str
    repeat: str
    weekday: str
    enabled: bool
    next_alarm_datetime: datetime | None
    skip_holiday: bool = False
    duration: int = 0
    snooze_minutes: int = 0
    end_at: str = ""
    snooze_limit: int = 3
    custom_desc: str = ""

# --- EOF ---
