# -*- coding: utf-8 -*-
"""アプリ全体で共有する定数と辞書定義"""
#########################
# Author: F.Kurokawa
# 共通定義ファイル（定数・辞書構造集中管理）
#########################

# ------------------------------------------
# 🔹 デフォルトサウンド設定
# ------------------------------------------
from pathlib import Path
from typing import Any, Final

from env_paths import BASE_DIR

DEFAULT_SOUND: Path = BASE_DIR / "sound" / "Alarm01.wav"
# ------------------------------------------
# 🔹 曜日ラベル（0=月〜6=日）
# ------------------------------------------
WEEKDAY_LABELS: list[str] = ["月", "火", "水", "木", "金", "土", "日"]
# 変換用
WEEKDAY_TO_INDEX: dict[str, int] = {label: i for i, label in enumerate(WEEKDAY_LABELS)}
INDEX_TO_WEEKDAY: dict[int, str] = {i: label for i, label in enumerate(WEEKDAY_LABELS)}

# ------------------------------------------
# 🔹 繰り返しパターン辞書(カスタムダイアログ表示用)
# ------------------------------------------

# -----------------------------
# 何週おき（内部値）
# -----------------------------
WEEKS_INTERNAL: list[int] = [1, 2, 3, 4, 5]

# -----------------------------
# 表示用（GUI）
# -----------------------------
WEEKS_DISPLAY: dict[int, str] = {
    1: "毎週",
    2: "隔週（2週おき）",
    3: "3週おき",
    4: "4週おき",
    5: "5週おき",
}

# 表示 → 内部値
REPEAT_INTERNAL: dict[str, str] = {
    "単発": "single",
    "毎日": "daily",
    "毎週": "weekly",
    "毎月": "monthly",
    "カスタム": "custom",
}

# 内部値 → 表示
REPEAT_DISPLAY: dict[str, str] = {
    "single": "単発",
    "daily": "毎日",
    "weekly": "毎週",
    "monthly": "毎月",
    "custom": "カスタム",
}

# GUI のドロップダウン用
REPEAT_OPTIONS_GUI: list[str] = list(REPEAT_INTERNAL.keys())

# GUI の曜日一覧
WEEKDAY_OPTIONS_GUI: list[str] = WEEKDAY_LABELS

# -------- カスタムダイアログ表示用 ------------------
# GUI ドロップダウン用（表示）
WEEKS_CUSTOM_GUI: list[str] = list(WEEKS_DISPLAY.values())
# ["毎週", "隔週（2週おき）", "3週おき", "4週おき", "5週おき"]

# 内部用（数値）
WEEKS_CUSTOM_INTERNAL: list[int] = list(WEEKS_DISPLAY.keys())
# [1, 2, 3, 4, 5]

# ------------------------------------------
# 🔹 🔑 Alarm 基本キー定義(AlarmInternal専用)
# ------------------------------------------
ALARM_INTERNAL_KEYS: Final[set[str]] = {
    "id",
    "name",
    "datetime",
    "repeat",
    "weekday",
    "week_of_month",
    "interval_weeks",
    "base_date",
    "custom_desc",
    "enabled",
    "sound",
    "skip_holiday",
    "duration",
    "snooze_minutes",
    "snooze_repeat_limit",
    "snooze_limit",
}
# =========================
# 🔧 デフォルト値（設計値）
# =========================
# DEFAULT_SNOOZE_MINUTES: Final[int] = 5
# DEFAULT_SNOOZE_LIMIT: Final[int] = 3
# ------------------------------------------
# 🔹 🔑 AlarmState 基本キー定義(AlarmStateInternal専用)
# ------------------------------------------
ALARM_STATE_KEYS: Final[set[str]] = {
    "id",
    "_snoozed_until",
    "_snooze_count",
    "_triggered",
    "_triggered_at",
    "_last_fired_at",
}


# ------------------------------------------
# 🔹 JSON・UI共用 構造（任意・開発補助）
# ------------------------------------------
ALARM_JSON_UI_KEYS: Final[set[str]] = {
    "id",  # 行識別子（必ず先頭）
    "name",  # 表示名
    "date",  # YYYY-MM-DD
    "time",  # HH:MM
    "repeat",  # single / daily / weekly / custom ...
    "weekday",  # [0,1,4] など
    "week_of_month",  # [1,3] など
    "interval_weeks",  # 何週おき
    "base_date",  # custom の基準日
    "custom_desc",  # カスタム説明文
    "enabled",  # ON/OFF
    "sound",  # WAV ファイル
    "skip_holiday",  # True/False
    "duration",  # 再生秒数
    "snooze_minutes",  # 初スヌーズ分
    "snooze_limit",  # 回数上限
}

STANDBY_KEYS: Final[set[str]] = {
    "id",
    "_snoozed_until",  # ISO8601
    "_snooze_count",  # 現在のカウント
    "_triggered",  # 鳴動中か？
    "_triggered_at",  # 鳴動開始時刻（ISO8601）
    "_last_fired_at",  # 最終鳴動時刻（ISO8601）
}

# ------------------------------------------
# 🔹 正規化アラームテンプレート（JsonEditor / AlarmManager 共通）
# ------------------------------------------
# AlarmJson/AlarmUI共用
ALARM_TEMPLATE: dict[str, Any] = {
    "id": 0,
    "name": "",
    "date": "",
    "time": "",
    "repeat": "single",
    "weekday": [],
    "week_of_month": [],
    "interval_weeks": 1,
    "base_date": "",
    "custom_desc": "",
    "enabled": False,
    "sound": "",
    "skip_holiday": False,
    "duration": 10,
    "snooze_minutes": 10,
    "snooze_limit": 3
}

# AlarmStateInternal
STANDBY_TEMPLATE: dict[str, Any] = {
    "id": 0,
    "_snoozed_until": None,
    "_snooze_count": 0,
    "_triggered": False,
    "_triggered_at": None,
    "_last_fired_at": None,
}

# ------------------------------------------
# 🔹 一覧表カラム名（GUI表示用）
# ------------------------------------------
# 設定ウインドウのアラーム一覧表カラム
COLUMN_BASE = (
    "id",
    "name",
    "date",
    "time",
    "repeat",
    "weekday",
    "enabled",
    "skip_holiday",
    "snooze_limit",
    "custom_desc",
)
# 設定ウインドウのアラーム一覧表カラム名変換
COLUMN_LABELS: dict[str, str] = {
    "id": "ID",
    "name": "アラーム名",
    "date": "日付",
    "time": "時刻",
    "repeat": "繰返し",
    "weekday": "曜日",
    "enabled": "有効",
    "skip_holiday": "祝日ｽｷｯﾌﾟ",
    "snooze_limit": "ｽﾇｰｽﾞ上限",
    "custom_desc": "詳細設定",
}
# ================以下はまだ手を付けない===========================
# ------------------------------------------
# 🔹 json_editor.py 用：ALARM_KEYS 日本語対応名
# ------------------------------------------
COLUMN_LABELS_EDITOR: dict[str, str] = {
    "id": "ID",
    "name": "アラーム名",
    "date": "日付",
    "time": "時刻",
    "repeat": "繰り返し",
    "weekday": "曜日",
    "week_of_month": "第n週",
    "interval_weeks": "間隔(週)",
    "base_date": "基準日",
    "enabled": "有効",
    "custom_desc": "詳細設定",
    "sound": "音ファイル",
    "skip_holiday": "祝日スキップ",
    "duration": "再生秒数",
    "snooze_minutes": "初回スヌーズ",
    "snooze_limit": "スヌーズ上限",
    "_snooze_count": "現在スヌーズ回数",
    "_snoozed_until": "スヌーズ再開時刻",
    "_triggered": "鳴動中フラグ",
    "_triggered_at": "鳴動開始時刻",
    "_last_fired_at": "最終鳴動時刻",
}
