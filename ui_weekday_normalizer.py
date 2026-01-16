# -*- coding: utf-8 -*-
"""CUIの入力を正規化する"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################

import unicodedata

# 曜日ラベル定義
WEEKDAY_LABELS: list[str] = ["月", "火", "水", "木", "金", "土", "日"]
WEEKDAY_TO_INDEX: dict[str, int] = {label: i for i, label in enumerate(WEEKDAY_LABELS)}
INDEX_TO_WEEKDAY: dict[int, str] = {i: label for i, label in enumerate(WEEKDAY_LABELS)}


def normalize_weekday_list(text: str | None) -> list[int] | None:
    """
    曜日入力を正規化して list[int] (0=月〜6=日) を返す
    例:
      "0,2,5" → [0,2,5]
      "火、木、土" → [1,3,5]
      "０、火,土" → [0,5]
    """
    if not text:
        return []

    # 1. 全角→半角（数字・記号）
    text = unicodedata.normalize("NFKC", text)

    # 2. 日本語読点をカンマに統一
    text = text.replace("、", ",")

    result: list[int] = []

    for part in text.split(","):
        part: str = part.strip()
        if not part:
            continue

        # 数字指定（0〜6）
        if part.isdigit():
            n = int(part)
            if 0 <= n <= 6:
                result.append(n)
            continue

        # 曜日ラベル指定（例: 火）
        if part in WEEKDAY_TO_INDEX:
            result.append(WEEKDAY_TO_INDEX[part])

    return sorted(set(result))
