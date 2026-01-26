# -*- coding: utf-8 -*-
"""UI用、文字列変換ユーティリティ"""
#########################
# Author: F.Kurokawa
# Description:
# (CUI/GUI共通) 文字列操作ユーティリティ
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

# =========================================================
# 🔹 UI(Alarm.name専用)文字列操作ユーティリティ
# =========================================================

def normalize_alarm_name(text: str | None) -> str:
    """
    alarm.name 用 正規化
    - None → ""
    - 前後空白削除
    - 全角/半角ゆらぎ吸収（NFKC）
    - 空白正規化
    """
    if text is None:
        return ""

    s: str = unicodedata.normalize("NFKC", text) # 全角→半角
    s = normalize_whitespace(s)
    return s.strip()


def validate_alarm_name(text: str) -> list[str]:
    """
    alarm.name の内容をチェックし、警告メッセージを返す
    ※ 空なら空リスト
    """
    warnings: list[str] = []

    if not text:
        warnings.append("アラーム名が空です")

    # 半角カタカナ検出
    if any("ｦ" <= ch <= "ﾟ" for ch in text):
        warnings.append("半角カタカナが含まれています")

    # 制御文字検出
    if any(ord(ch) < 32 for ch in text):
        warnings.append("制御文字が含まれています")

    # 極端に長い名前
    if len(text) > 100:
        warnings.append("アラーム名が長すぎます")

    return warnings
