# pyright: strict
# -*- coding: utf-8 -*-
# pylint: disable=W0212
"""
⚠ utils.py の利用ルール ⚠
- UI / Alarm / Storage を import しない
- 型変換・純粋関数のみ置く
- 新規追加は原則禁止
"""
#########################
# Author: F.Kurokawa
# Description:
# 共通関数
#########################
# 標準ライブラリ
import os
from datetime import date, datetime, time
from pathlib import Path
from tkinter import filedialog
from typing import Any, Dict, List, Optional, cast

# 自作定数モジュール
from constants import DEFAULT_SOUND

# 自作モジュール
from env_paths import BASE_DIR, CONFIG_PATH

# =========================================================
# 🔹 1. 文字列・日付・時刻の基本ユーティリティ（頻度高）
# =========================================================
# ---- datetime ⇄ date/time ----


def datetime_to_dict(dt: Optional[datetime]) -> Dict[str, str]:
    """datetimeを{"date": "...", "time": "..."}のDictに変換"""
    if dt is None:
        return {}

    dt = dt.replace(second=0, microsecond=0)
    date_: date = dt.date()
    time_: time = dt.time()

    return {"date": date_.isoformat(), "time": time_.isoformat()}


def dict_to_datetime(date_str: str, time_str: str) -> datetime:
    """{"date": "...", "time": "..."} -> datetime"""
    return datetime.fromisoformat(f"{date_str}T{time_str}")


def str_to_datetime(dt: str) -> datetime:
    """ISO文字列 -> datetime"""
    return datetime.fromisoformat(dt)


def combine_datetime(date_str: str, time_str: str) -> datetime:
    """日付文字列と時刻文字列を結合して datetime に変換"""
    return datetime.fromisoformat(f"{date_str}T{time_str}")


# =========================================================
# 🔹 3. パス関連ユーティリティ（起動時に使用）
# =========================================================
APP_DIR: Path = BASE_DIR
CONFIG_FILE: Path = CONFIG_PATH  # 実ファイル名だけを持つ

# =========================================================
# 🔹 4. アプリ設定関連ユーティリティ
# =========================================================

def select_sound_file() -> str:
    """音声ファイルを選択してパスを返す（GUI依存）"""
    selected_file: str = filedialog.askopenfilename(
        title="アラーム音を選択してください",
        initialdir=os.path.dirname(DEFAULT_SOUND),
        filetypes=[
            ("WAVファイル", "*.wav"),
            ("MP3ファイル", "*.mp3"),
            ("すべてのファイル", "*.*"),
        ],
    )

    if selected_file:
        print(f"選択されたファイル: {selected_file}")
        return selected_file

    print("ファイルが選択されませんでした。デフォルト音を使用します。")
    return str(DEFAULT_SOUND)


def get_data_dir() -> Path:
    """データ保存用のフォルダ（アプリと同じ階層）"""
    base: Path = APP_DIR
    data_dir: Path = base / "alarm"
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


# --------------------------------------
# Dict対応関数(Keyの順序安定化)
# --------------------------------------
def normalize_alarm_input_dict(
    data: Dict[str, Any], template: Dict[str, Any]
) -> Dict[str, Any]:
    """
    ALARM_TEMPLATE の key 順に従って data を並び替える。
    足りないキーは template のデフォルト値で補完する。
    ※ JSON 保存前に必ず通すことで、key の順序が安定します。
    """
    normalized: Dict[str, Any] = {}

    for key, default_value in template.items():
        value: Any = data.get(key, default_value)

        # list や dict の場合はコピーにしておく方が安全
        if isinstance(value, list):
            normalized[key] = list(cast(List[Any], value))
        elif isinstance(value, dict):
            normalized[key] = dict(cast(Dict[str, Any], value))
        else:
            normalized[key] = value

    return normalized
