# -*- coding: utf-8 -*-
"""UI用、文字列変換ユーティリティ"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
# 標準ライブラリ
import unicodedata
from typing import Any, Optional


def to_hankaku(text: Optional[str]) -> str:
    """全角文字を半角に変換（数字・英字・記号のみ）"""
    if text is None:
        return ""
    return unicodedata.normalize("NFKC", text)


def safe_str(value: Any) -> str:
    """Any → str 安全変換（None→空文字）"""
    if value is None:
        return ""
    return str(value)


def is_empty(text: str | None) -> bool:
    """文字列が空かどうか判定（Noneまたは空白のみ）"""
    if text is None:
        return True
    return text.strip() == ""


def normalize_whitespace(text: str) -> str:
    """連続する空白を単一の空白に正規化"""
    return " ".join(text.split())


def strip_or_none(text: str | None) -> str | None:
    """文字列の前後の空白を削除、空文字ならNoneを返す"""
    if text is None:
        return None
    s: str = text.strip()
    return s if s else None
