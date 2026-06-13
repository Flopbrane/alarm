# -*- coding: utf-8 -*-
"""CUI の repeat 入力を内部値へ正規化する。"""
from __future__ import annotations

import unicodedata

from constants import DEFAULT_REPEAT_INTERNAL

_REPEAT_ALIASES: dict[str, str] = {
    "単発": "single",
    "単体": "single",
    "一回": "single",
    "1回": "single",
    "single": "single",
    "once": "single",
    "毎日": "daily",
    "日次": "daily",
    "daily": "daily",
    "毎週": "weekly",
    "週次": "weekly",
    "weekly": "weekly",
    "毎月": "monthly",
    "月次": "monthly",
    "monthly": "monthly",
    "月間": "monthly",
    "日おき": "interval_days",
    "日毎": "interval_days",
    "日ごと": "interval_days",
    "intervaldays": "interval_days",
    "interval_days": "interval_days",
    "カスタム": "custom",
    "custom": "custom",
}


def normalize_repeat_input(text: str | None, default: str = DEFAULT_REPEAT_INTERNAL) -> str:
    """repeat の入力揺れを内部値へ正規化する。"""
    if text is None:
        return default

    normalized: str = unicodedata.normalize("NFKC", text).strip().lower()
    compact: str = (
        normalized.replace(" ", "")
        .replace("　", "")
        .replace("・", "")
        .replace("_", "")
        .replace("-", "")
    )
    return _REPEAT_ALIASES.get(compact, default)
