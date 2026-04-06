# -*- coding: utf-8 -*-
"""logファイルを読み込み、重要ポイントを表示する"""
#########################
# Author: F.Kurokawa
# Description:
# logファイルを読み込み、重要ポイントを表示する
#########################
# log_searcher.py

import json
from pathlib import Path
from typing import Any


def load_logs(path: Path) -> list[dict[str, Any]]:
    """ログファイルを読み込む（JSONL形式）"""
    logs: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return logs


def detect_trace_jump(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """traceジャンプを検出する"""
    results: list[dict[str, Any]] = []
    prev_trace: str | None = None

    for log in logs:
        trace: str | None = log.get("trace_id")

        if prev_trace and trace != prev_trace:
            results.append(_format_event(log, "TRACE_JUMP", "trace_id changed"))

        prev_trace = trace

    return results


def detect_errors(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """エラーログを検出する"""
    results: list[dict[str, Any]] = []

    for log in logs:
        if log.get("level") in ("ERROR", "CRITICAL"):
            results.append(
                _format_event(
                    log,
                    log.get("level", "UNKNOWN"),
                    log.get("what", {}).get("message"),
                )
            )

    return results


def summarize(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ログを要約して重要ポイントを抽出する"""
    results: list[dict[str, Any]] = []
    results.extend(detect_trace_jump(logs))
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
