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
from dataclasses import dataclass, field
from typing import List, Optional, Union, cast

# 自作モジュール
from constants import DEFAULT_SOUND


@dataclass
class AlarmUI:
    """入力専用のdataclass"""

    id: Optional[int] = None  # 行識別子（必ず先頭）
    name: str = ""  # 表示名
    date: str = ""  # YYYY-MM-DD
    time: str = ""  # HH:MM
    repeat: str = "none"  # none / daily / weekly / custom ...
    weekday: List[Union[int, str]] = field(
        default_factory=lambda: cast(List[Union[int, str]], [])
    )  # [0,1,4] など
    week_of_month: List[int] = field(
        default_factory=lambda: cast(List[int], [])
    )  # [1,3] など
    interval_weeks: int = 1  # weekly_x の x
    base_date: Optional[str] = ""  # custom の基準日
    custom_desc: str = ""  # カスタム説明文

    enabled: bool = True  # ON/OFF
    sound: str = str(DEFAULT_SOUND)  # WAV ファイル
    skip_holiday: bool = False  # True/False

    duration: int = 30  # 再生秒数
    snooze_minutes: int = 10  # 初スヌーズ分
    snooze_repeat_limit: int = 10  # 回数上限


@dataclass(frozen=True)
class AlarmStateView:
    """状態表示用のdataclass"""
    id: Optional[int] = None  # 行識別子（必ず先頭）
    snoozed_until: Optional[str] = None  # ISO文字列
    snooze_count: int = 0 # スヌーズ回数
    triggered: bool = False # 鳴動中か？
    triggered_at: Optional[str] = None  # 鳴動開始時刻
    last_fired_at: Optional[str] = None  # 最終鳴動時刻

# --- EOF ---
