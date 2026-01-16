# -*- coding: utf-8 -*-
"""UI用、曜日表示ユーティリティ"""
#########################
# Author: F.Kurokawa
# Description:
# UI用、曜日表示ユーティリティ(チェック済み)
#########################
# 標準ライブラリ
from typing import List

# 自作定数モジュール
from constants import WEEKDAY_LABELS


# ===============================
# 🔹 GUI用、曜日表示ユーティリティ
# ===============================
def weekday_to_str(weekday_list: List[int]) -> str:
    """例: [0,2,4] → '月水金'"""
    if not weekday_list:
        return ""
    return "".join(WEEKDAY_LABELS[i] for i in weekday_list)

def compact_str_to_weekday_list(weekday_str: str) -> List[int]:
    """例: '月水金' → [0,2,4]"""
    result: List[int] = []
    for ch in weekday_str:
        if ch in WEEKDAY_LABELS:
            result.append(WEEKDAY_LABELS.index(ch))
    return result

# ===============================
# 🔹 CUI用、曜日表示ユーティリティ
# ===============================
def weekday_list_to_display_str(weekday_list: List[int]) -> str:
    """例: [0,2,4] → '月、水、金'"""
    if not weekday_list:
        return "なし"
    return "、".join(WEEKDAY_LABELS[i] for i in weekday_list)

def display_str_to_weekday_list(weekday_str: str) -> List[int]:
    """例: '月、水、金' → [0,2,4]"""
    result: List[int] = []
    for part in weekday_str.split("、"):
        part: str = part.strip()
        if part in WEEKDAY_LABELS:
            result.append(WEEKDAY_LABELS.index(part))
    return result
