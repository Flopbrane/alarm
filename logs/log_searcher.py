# -*- coding: utf-8 -*-
"""logファイルを読み込み、重要ポイントを表示する"""
#########################
# Author: F.Kurokawa
# Description:
# logファイルを読み込み、重要ポイントを表示する
#########################
# log_searcher.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Any


def load_logs(path: Path) -> list[dict[str, Any]]:
    """logファイルを読み込む"""
    logs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            logs.append(json.loads(line))
    return logs


def detect_trace_jumps(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """traceジャンプを検出する（前の行とtrace_idが変わったら）"""
    results: list[dict[str, Any]] = []
    prev: str | None = None

    for row in logs:
        current: str | None = row.get("trace_id")

        if prev is not None and current != prev:
            results.append(
                {
                    "type": "TRACE_JUMP",
                    "from": prev,
                    "to": current,
                    "row": row,
                }
            )

        prev = current

    return results


def find_errors(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """エラーログを検出する（levelがERRORまたはCRITICALの行）"""
    return [row for row in logs if row.get("level") in ("ERROR", "CRITICAL")]


def detect_errors(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """エラーログを検出する"""
    results: list[dict[str, Any]] = []

    for log in logs:
        if log.get("level") in ("ERROR", "CRITICAL"):
            what_raw: dict[str, Any] | None = log.get("what", {})

            if isinstance(what_raw, dict):
                message: str | None = what_raw.get("message")
            else:
                message = None

            message = message if isinstance(message, str) else ""

            results.append(
                _format_event(
                    log,
                    log.get("level", "UNKNOWN"),
                    message,
                )
            )

    return results


def summarize(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ログを要約して重要ポイントを抽出する"""
    results: list[dict[str, Any]] = []
    results.extend(detect_trace_jumps(logs))
    results.extend(detect_errors(logs))

    return sorted(results, key=lambda x: x["time"])


# 🔥 共通フォーマット関数（重要）
def _format_event(log: dict[str, Any], type_: str, message: str) -> dict[str, Any]:
    """ログイベントを共通フォーマットに変換する"""
    return {
        "time": log.get("time"),
        "type": type_,
        "trace_id": log.get("trace_id"),
        "message": message,
        "raw": log,  # ← UIで使う
    }
