# -*- coding: utf-8 -*-
"""UIで,年月日・時刻の入力値が異常なときに
メッセージを出して再入力を促すか、
無記述のときにdatetime.now()を使用して
自動入力するモジュール
"""
#########################
# Author: F.Kurokawa
# Description:
# UIの入力文字訂正(CUI入力値チェック用/チェック済み)
#########################

import datetime
import re
import unicodedata

from utils.text_utils import to_hankaku


# ==============================
# ⚠ 日付・時刻 バリデーションユーティリティ
# (CUI入力値チェック用)
# ==============================
def validate_date(text: str) -> str | None:
    """
    YYYY-MM-DD / YYYY/MM/DD のみ許可
    それ以外は ValueError(例：令和Y年m月d日などの和暦はNG)
    """
    normalized: str | None = normalize_date(to_hankaku(text))
    if normalized is None:
        return None
    datetime.datetime.strptime(normalized, "%Y-%m-%d")
    return normalized

def validate_time(text: str) -> str | None:
    """HH:MM 形式ならOK、ダメなら None"""
    normalized: str | None = normalize_time(to_hankaku(text))
    if normalized is None:
        return None

    datetime.datetime.strptime(normalized, "%H:%M")
    return normalized

# ==============================
# ⚠ 日付・時刻 正規化ユーティリティ
# (CUI入力値チェック用)
# ==============================

def normalize_commas(text: str) -> str:
    """日本語表記の'、'を','に変換する"""
    text = unicodedata.normalize("NFKC", text)
    return text.replace("、", ",")


def normalize_date(text: str) -> str | None:
    """
    CUI or Json_Editer 用：
    YYYY-MM-DD / YYYY/MM/DD のみ許可
    それ以外は ValueError(例：令和Y年m月d日などの和暦はNG)
    海外表記の
    MM/DD/YY   → 曖昧：弾く
    DD/MM/YY   → 文化依存：弾く
    令和◯年◯月◯日 → 別途専用処理が必要：弾く
    """
    text = text.strip()

    if not text:
        return datetime.datetime.now().strftime("%Y-%m-%d")

    patterns: list[tuple[str, str]] = [
        ("%Y-%m-%d", r"^\d{4}-\d{1,2}-\d{1,2}$"),
        ("%Y/%m/%d", r"^\d{4}/\d{1,2}/\d{1,2}$"),
        ("%y-%m-%d", r"^\d{2}-\d{1,2}-\d{1,2}$"),
        ("%y/%m/%d", r"^\d{2}/\d{1,2}/\d{1,2}$"),
        ("%Y%m%d", r"\d{8}"),
        ("%y%m%d", r"\d{6}"),
        ("%y%m%d", r"\d{5}"),
        ("%y%m%d", r"\d{4}"),
    ]

    for fmt, pat in patterns:
        if re.fullmatch(pat, text):
            try:
                dt: datetime.datetime = datetime.datetime.strptime(text, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                print("日付形式は YYYY-MM-DD で入力してください")
                continue
    print("日付形式は YYYY-MM-DD で入力してください")
    # すべて失敗
    return None


def normalize_time(text: str) -> str | None:
    """
    日付入力を正規化して HH:MM を返す
    失敗時は今日の日付
    """
    text = text.strip()

    if not text:
        return datetime.datetime.now().strftime("%H:%M")

    patterns: list[tuple[str, str]] = [
        ("%H:%M", r"^\d{1,2}:\d{1,2}$"),  # 9:5 / 09:05 / 9:05 / 12:3
        ("%H %M", r"^\d{1,2}\s+\d{1,2}$"),  # 9 5 / 09 05
        ("%H%M", r"^\d{2,4}$"),  # 930 / 0930 / 1230
    ]

    for fmt, pat in patterns:
        if re.fullmatch(pat, text):
            try:
                dt: datetime.datetime = datetime.datetime.strptime(text, fmt)
                return dt.strftime("%H:%M")
            except ValueError:
                print("時刻形式は HH:MM で入力してください")
                continue

    # すべて失敗
    return None


def normalize_base_date(
    base_date: str | datetime.date | datetime.datetime,
    alarm_time: datetime.datetime,
    ) -> datetime.datetime | None:
    """
    UI / JSON / 手入力由来の壊れた base_date を
    内部仕様の datetime に修復する。
    """
    if isinstance(base_date, str):
        try:
            base_date = datetime.datetime.fromisoformat(base_date)
        except ValueError:
            return None

    if not isinstance(base_date, datetime.datetime):
        try:
            base_date = datetime.datetime.combine(base_date, alarm_time.time())
        except (TypeError, AttributeError, ValueError):
            return None

    return base_date.replace(
        hour=alarm_time.hour,
        minute=alarm_time.minute,
        second=0,
        microsecond=0,
    )
