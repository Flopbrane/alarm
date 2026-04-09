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


def detect_reboot_events(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """システム再起動イベントを検出する（what.messageがsystem_reboot_detectedの行）"""
    results: list[dict[str, Any]] = []

    for log in logs:
        if log.get("what", {}).get("message") == "system_reboot_detected":
            results.append(
                _build_event(
                    log,
                    "REBOOT",
                    "system reboot detected",
                )
            )

    return results


def detect_trace_jumps(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """traceジャンプを検出する（前の行とtrace_idが変わったら）"""
    results: list[dict[str, Any]] = []
    prev: str | None = None

    for row in logs:
        current: str | None = row.get("trace_id")

        if prev is not None and current != prev:
            results.append(
                _build_event(
                    row,
                    "TRACE_JUMP",
                    "trace_id changed",
                    data={"from": prev, "to": current},
                )
            )

        prev = current  # ← ★ここに移動（超重要）

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
                _build_event(
                    log,
                    f"{log.get('level')} detected",
                    message,
                )
            )

    return results


def detect_reboot(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """システム再起動イベントを検出する（what.messageがsystem_reboot_detectedの行）"""
    results: list[dict[str, Any]] = []

    for log in logs:
        message: str | None = log.get("what", {}).get("message")

        if message == "system_reboot_detected":
            results.append(
                _build_event(
                    log,
                    "REBOOT",
                    "system reboot detected",
                )
            )

    return results


def summarize(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """ログを要約して重要ポイントを抽出する"""
    results: list[dict[str, Any]] = []
    results.extend(detect_trace_jumps(logs))
    results.extend(detect_errors(logs))
    results.extend(detect_reboot(logs))

    return sorted(results, key=lambda x: x["time"])


# 🔥 共通フォーマット関数（重要）
def _build_event(
    log: dict[str, Any],
    type_: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """イベント変換関数（解析用）

    ★★ ログレコード（LogRecord）をイベント（Event）に変換する関数

    ・記録されたログを解釈し、意味のあるイベントに変換する層
    ・分析・可視化のためのデータ整形を行う
    """
    return {
        "time": log.get("time"),
        "type": type_,
        "trace_id": log.get("trace_id"),
        "message": message,
        "data": data or {},
        "raw": log,
    }
