# -*- coding: utf-8 -*-
"""アプリ全体で共有する定数と辞書定義（dataclass運用版）"""
#########################
# Author: F.Kurokawa
# Description:
# 共通定義ファイル（定数・辞書構造集中管理）
#########################

from __future__ import annotations

from pathlib import Path
from typing import Final

from env_paths import BASE_DIR

# ==========================================================
# 🔊 サウンド・基本パス
# ==========================================================
DEFAULT_SOUND: Path = BASE_DIR / "sound" / "Alarm01.wav"
# デフォルトのアラーム音ファイルパス
# ==========================================================
# 🗓️ 曜日（0=月〜6=日）
# ==========================================================
WEEKDAY_LABELS: Final[list[str]] = ["月", "火", "水", "木", "金", "土", "日"]

# 変換用（CUI入力補正・GUI表示で使用）
WEEKDAY_TO_INDEX: Final[dict[str, int]] = {label: i for i, label in enumerate(WEEKDAY_LABELS)}
INDEX_TO_WEEKDAY: Final[dict[int, str]] = {i: label for i, label in enumerate(WEEKDAY_LABELS)}

# GUI の曜日一覧（ドロップダウン等）
WEEKDAY_OPTIONS_GUI: Final[list[str]] = list(WEEKDAY_LABELS)

# ==========================================================
# 🔁 repeat（表示 ↔ 内部値）
# ==========================================================
# 表示 → 内部値（UI/CUI入力の正規化用）
REPEAT_INTERNAL: Final[dict[str, str]] = {
    "単発": "single",
    "毎日": "daily",
    "毎週": "weekly",
    "毎月": "monthly",
    "◯日おき": "interval_days",
    "カスタム": "custom",
}

# 内部値 → 表示（UI表示用）
REPEAT_DISPLAY: Final[dict[str, str]] = {
    "single": "単発",
    "daily": "毎日",
    "weekly": "毎週",
    "monthly": "毎月",
    "interval_days": "◯日おき",
    "custom": "カスタム",
}
# 内部値のデフォルト値
DEFAULT_REPEAT_INTERNAL: Final[str] = "single"


# GUI のドロップダウン用（表示文字列）
REPEAT_OPTIONS_GUI: Final[list[str]] = list(REPEAT_INTERNAL.keys())
# 表示->内部値変換（デバッグ・内部処理用）
REPEAT_OPTIONS_INTERNAL: Final[list[str]] = list(REPEAT_INTERNAL.values())

# ==========================================================
# 📆 「何週おき」表示（interval_weeks）
# ==========================================================
# 内部値（1〜5週おき）
WEEKS_INTERNAL: Final[tuple[int, ...]] = (1, 2, 3, 4, 5)

# 表示用（GUI）
WEEKS_DISPLAY: Final[dict[int, str]] = {
    1: "毎週",
    2: "隔週（2週おき）",
    3: "3週おき",
    4: "4週おき",
    5: "5週おき",
}
# デフォルト値
DEFAULT_INTERVAL_WEEKS: Final[int] = 1
# GUI ドロップダウン用（表示）
WEEKS_CUSTOM_GUI: Final[list[str]] = [WEEKS_DISPLAY[i] for i in WEEKS_INTERNAL]
# 内部用（数値）
WEEKS_CUSTOM_INTERNAL: Final[list[int]] = list(WEEKS_DISPLAY.keys())


# ==========================================================
# 📋 GUI 一覧表（カラム定義）
# ==========================================================
COLUMN_BASE: Final[tuple[str, ...]] = (
    "id",  # 一覧表示用ID(実稼働時は削除予定)
    "name",
    "date",
    "time",
    "repeat",
    "weekday",
    "enabled",
    "skip_holiday",
    "duration_time",
    "snooze_limit",
    "end_at",
    "custom_desc",
)

COLUMN_LABELS: Final[dict[str, str]] = {
    "id": "ID", # 一覧表示用ID(実稼働時は削除予定)
    "name": "アラーム名",
    "date": "日付",
    "time": "時刻",
    "repeat": "繰返し",
    "weekday": "曜日",
    "enabled": "有効/無効",
    "skip_holiday": "祝日スキップ",
    "duration_time": "再生分数",
    "snooze_limit": "スヌーズ回数上限",
    "end_at": "アラーム有効期限終了日時",
    "custom_desc": "詳細設定",
}


# ==========================================================
# 🧾 json_editor.py 用：日本語ラベル（表示辞書）
# ※ dataclass移行後も「表示名辞書」としては有用なので残す
# ==========================================================
COLUMN_LABELS_EDITOR: Final[dict[str, str]] = {
    "id": "ID",
    "name": "アラーム名",
    "date": "日付",
    "time": "時刻",
    "repeat": "繰り返し",
    "weekday": "曜日",
    "week_of_month": "第n週",
    "interval_weeks": "間隔(週)",
    "interval_days": "間隔(日)",
    "base_date": "基準日",
    "enabled": "有効",
    "custom_desc": "詳細設定",
    "sound": "音ファイル",
    "skip_holiday": "祝日スキップ",
    "duration": "再生秒数",
    "snooze_minutes": "初回スヌーズ",
    "snooze_limit": "スヌーズ上限",
    "end_at": "アラーム有効期限終了日時",
    "_snooze_count": "現在スヌーズ回数",
    "_snoozed_until": "スヌーズ再開時刻",
    "_triggered": "鳴動中フラグ",
    "_triggered_at": "鳴動開始時刻",
    "_last_fired_at": "最終鳴動時刻",
}
