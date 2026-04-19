# -*- coding: utf-8 -*-
# pylint: disable=W0718
"""表示整形のモジュール"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from logs.time_utils import to_jst_datetime
from logs.log_types import Event, LogDict, LogWhere


class LogRenderer:
    """ログ表示専用クラス（整形エンジン🔥）"""

    def __init__(self, *, indent: int = 2, key_width: int = 12) -> None:
        self.indent: str = " " * indent
        self.key_width: int = key_width
        # フォント指定
        self.font_title: tuple[str, int, str] = ("Yu Gothic UI", 12, "bold")
        self.font_normal: tuple[str, int] = ("Yu Gothic UI", 10)
        self.font_bold_normal: tuple[str, int, str] = ("Yu Gothic UI", 10, "bold")
        self.font_mono: tuple[str, int] = ("Cascadia Code", 10)

    # =========================
    # 色付きRenderer
    # =========================
    def get_level_color(self, level: str) -> str:
        """色付き描画"""
        return {
            "DEBUG": "#888888",
            "INFO": "#000000",
            "WARNING": "#d97f00",
            "ERROR": "#d00000",
            "CRITICAL": "#800000",
            "REBOOT": "#0066cc",
        }.get(level, "#000000")

    # =========================
    # 🔹 message整形
    # =========================
    def format_message(self, msg: str) -> str:
        """messageの整形"""
        prefix: str
        rest: str
        # 👉 両対応（安全）
        if "→" in msg:
            sep = "→"
        elif "->" in msg:
            sep = "->"
        else:
            return msg

        prefix, rest = msg.split(sep, 1)

        try:
            # 🔥 シングルクォート対応
            json_like: str = re.sub(r"'", '"', rest.strip())
            data: dict[str, Any] = json.loads(json_like)
            pretty: str = json.dumps(data, indent=2, ensure_ascii=False)
            return f"{prefix.strip()}\n→\n{pretty}"

        except Exception:
            # 🔥 安全フォールバック
            pretty = (
                rest.strip()
                .replace(", '", ",\n  '")
                .replace("{", "{\n  ")
                .replace("}", "\n}")
            )
            return f"{prefix.strip()}\n→ {pretty}"

    # =========================
    # 🔹 時刻整形
    # =========================
    def format_time(self, value: Any) -> str:
        """時刻整形"""
        dt: datetime | None = to_jst_datetime(value)
        if dt and 2000 <= dt.year <= 2100:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(value)

    # =========================
    # 🔹 Context整形
    # =========================
    def build_context(self, context: dict[str, Any]) -> str:
        """context整形"""
        lines: list[str] = []
        for k, v in context.items():
            v: str = self.format_time(v)
            lines.append(f"{self.indent}{k:<{self.key_width}} : {v}")
        return "\n".join(lines)

    # =========================
    # 🔹 Event整形
    # =========================
    def build_event(self, data: dict[str, Any]) -> str:
        """イベント整形"""
        lines: list[str] = []
        for k, v in data.items():
            lines.append(f"{self.indent}{k:<{self.key_width}} : {v}")
        return "\n".join(lines)

    # ==========================
    # 🔹 詳細表示整形
    # ==========================
    def build_summary_parts(self, row: Event) -> list[tuple[str, str]]:
        """
        戻り値：[(テキスト, 色), ...]
        """
        raw: LogDict = row.raw

        level: str = row.level.name
        color: str = self.get_level_color(level)

        where: LogWhere = raw.get("where", {})

        parts: list[tuple[str, str]] = [
            (f"Type  : {row.type.name if row.type else '-'}", color),
            (f"Level : {level}", color),
            (f"Time(JST) : {self.format_time(row.time)}", "#000000"),
            (f"Time(UTC) : {row.time}", "#888888"),
            ("", ""),
        ]

        # 🔹 message
        msg = str(raw.get("what", {}).get("message", ""))
        msg: str = self.format_message(msg)
        # print("DEBUG:", row.raw)
        parts += [
            ("=== MESSAGE ===", "#0000aa"),
            (msg, "#000000"),
            ("", ""),
        ]

        # 🔹 where情報（これ重要🔥）
        parts += [
            (f"File : {where.get('file','')}", "#444444"),
            (f"Line : {where.get('line','')}", "#444444"),
            (f"Func : {where.get('function','')}", "#444444"),
            ("", ""),
        ]

        # 🔹 Event
        if row.data:
            parts.append(("--- Event ---", "#0066cc"))
            for k, v in row.data.items():
                parts.append((f"{self.indent}{k:<{self.key_width}} : {v}", "#000000"))
            parts.append(("", ""))

        # 🔹 Context
        context: dict[str, Any] = raw.get("context", {})
        if context:
            parts.append(("--- Context ---", "#0066cc"))
            for k, v in context.items():
                v: str = self.format_time(v)
                parts.append((f"{self.indent}{k:<{self.key_width}} : {v}", "#000000"))

        return parts
    # =========================
    # 🔹 Summary生成🔥
    # =========================
    def build_summary(self, row: Event) -> str:
        """サマリー整形"""
        raw: LogDict = row.raw

        event_type:  str = row.type.name if row.type else "-"
        level: str = row.level.name

        time_str: str = self.format_time(row.time)
        utc_time = str(row.time)

        where: LogWhere = raw.get("where", {})
        file_path = str(where.get("file", ""))
        line_no = str(where.get("line", ""))
        func = str(where.get("function", ""))

        message = str(raw.get("what", {}).get("message", ""))
        message: str = self.format_message(message)

        context_text: str = self.build_context(raw.get("context", {}))
        event_text: str = self.build_event(row.data)

        lines: list[str] = [
            f"Type  : {event_type}",
            f"Level : {level}",
            f"Time(JST) : {time_str}",
            f"Time(UTC) : {utc_time}",
            "",
            "=== MESSAGE ===",
            message,
            "",
            f"File : {file_path}",
            f"Line : {line_no}",
            f"Func : {func}",
            "",
        ]

        if event_text:
            lines += ["--- Event ---", event_text, ""]

        if context_text:
            lines += ["--- Context ---", context_text]

        return "\n".join(lines)

    # =========================
    # 🔹 RAW生成
    # =========================
    def build_raw(self, row: Event) -> dict[str, Any]:
        """RAW整形"""
        raw: LogDict = row.raw

        result: dict[str, Any] = {
            "level": raw.get("level"),
            "time": raw.get("time"),
            "trace_id": raw.get("trace_id"),
            "where": raw.get("where"),
            "what": raw.get("what"),
            "context": raw.get("context"),
        }

        if row.data:
            result |= {"event": row.data}

        return result
