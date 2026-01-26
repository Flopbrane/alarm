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
