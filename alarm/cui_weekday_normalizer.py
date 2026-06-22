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
WEEKDAY_ALIASES: dict[str, int] = {
    "月": 0, "月曜": 0, "月曜日": 0, "mon": 0, "monday": 0,
    "火": 1, "火曜": 1, "火曜日": 1, "tue": 1, "tues": 1, "tuesday": 1,
    "水": 2, "水曜": 2, "水曜日": 2, "wed": 2, "wednesday": 2,
    "木": 3, "木曜": 3, "木曜日": 3, "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "金": 4, "金曜": 4, "金曜日": 4, "fri": 4, "friday": 4,
    "土": 5, "土曜": 5, "土曜日": 5, "sat": 5, "saturday": 5,
    "日": 6, "日曜": 6, "日曜日": 6, "sun": 6, "sunday": 6,
}


def normalize_weekday_list(text: str | None) -> list[int]:
    """
    曜日入力を正規化して list[int] (0=月〜6=日) を返す
    例:
      "0,2,5" → [0,2,5]
      "火、木、土" → [1,3,5]
      "０、火,土" → [0,1,5]
    """
    if not text:
        return []

    # 1. 全角→半角（数字・記号）
    text = unicodedata.normalize("NFKC", text)

    if ("." or "．") in text:
        text = text.replace(".", ",").replace("．", ",")  # 小数点は区切りとみなす

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

        weekday_value: int | None = WEEKDAY_ALIASES.get(part.lower())
        if weekday_value is not None:
            result.append(weekday_value)

    return sorted(set(result))


def parse_weekdays_cui(raw: str | None) -> list[int]:
    """
    CUI入力の曜日指定を解釈して list[int] (0=月〜6=日) を返す
    例:
    "0,2,5" → [0,2,5]
    "火、木、土" → [1,3,5]
    "０、火,土" → [0,5]
    """
    # 1) 正規化して 0〜6 にする
    raw_safe: str = raw or ""
    wd: list[int] = normalize_weekday_list(raw_safe) or []

    # 2) “数字のみ”かつ 1〜7が含まれる場合は確認（曖昧対策）
    if raw_safe.strip() and _looks_numeric_only(raw_safe):
        nums: list[int] = _extract_ints(raw_safe)
        if any(1 <= n <= 7 for n in nums) and not any(n == 0 for n in nums):
            labels: str = ",".join(INDEX_TO_WEEKDAY[i] for i in wd)
            ans: str = input(f"曜日は {labels} と解釈します（0=月..6=日）。OK? (y/n): ")
            if ans.lower() != "y":
                raise ValueError("weekday input cancelled")

    # 3) 表示（黒川さん案）
    if wd:
        print("→ 曜日:", ",".join(INDEX_TO_WEEKDAY[i] for i in wd))
    else:
        print("→ 曜日指定なし")
    return wd

def _looks_numeric_only(text: str | None) -> bool:
    """数字・記号・空白のみで構成されているか？"""
    if not text:
        return False
    allowed_chars: set[str] = set("0123456789,、 \t")
    return all(c in allowed_chars for c in text)

def _extract_ints(text: str | None) -> list[int]:
    """テキストから整数を抽出する（数字以外は区切りとみなす）"""
    if not text:
        return []
    result: list[int] = []
    for part in text.split(","):
        part: str = part.strip()
        if not part:
            continue
        if part.isdigit():
            result.append(int(part))
    return result
