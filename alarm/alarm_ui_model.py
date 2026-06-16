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
from constants import DEFAULT_SOUND

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

    duration: int = 30  # 再生秒数
    snooze_minutes: int = 10  # 初スヌーズ分
    snooze_limit: int = 10  # 回数上限
    end_at: str | None = None  # アラームの終了日時（ISO文字列）(None の場合は無期限に鳴る)


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
    end_at: Optional[str | None] = None  # アラームの終了日時（ISO文字列）(None の場合は無期限に鳴る)


@dataclass(frozen=True)
class AlarmStateView:
    """状態表示用のdataclass
    このdataclassを所持しているのは、
    manager経由で、次回時刻計算された
    既存のアラームデータのみ。"""
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


# --- EOF ---
