# -*- coding: utf-8 -*-
"""ログ検索・分析機能"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

#########################
# Author: F.Kurokawa
# Description:
# logファイルを読み込み、重要ポイントを表示する
#########################

# =========================
# 型エイリアス
# =========================
LogDict = dict[str, Any]

# =========================
# 日付抽出（YYYY-MM-DD）
# =========================
DATE_PATTERN: re.Pattern[str] = re.compile(r"\d{4}-\d{2}-\d{2}")


def extract_date_from_path(p: Path) -> date | None:
    """ファイル名から日付を抽出する（YYYY-MM-DD）"""
    match: re.Match[str] | None = DATE_PATTERN.search(p.stem)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group())
    except ValueError:
        return None


# =========================
# ログファイル取得（NEW🔥）
# =========================
def get_log_files(
    log_dir: Path,
    start: date | None = None,
    end: date | None = None,
) -> list[Path]:
    """指定した期間のログファイルを取得する"""
    result: list[Path] = []

    for p in log_dir.iterdir():
        if not p.is_file():
            continue

        if p.suffix.lower() not in (".jsonl", ".log"):
            continue

        file_date: date | None = extract_date_from_path(p)
        if file_date is None:
            continue

        if start and file_date < start:
            continue
        if end and file_date > end:
            continue

        result.append(p)

    return result


# =========================
# ログ読み込み
# =========================
def load_logs(path: Path) -> list[LogDict]:
    """ログファイルを読み込む"""
    logs: list[LogDict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            logs.append(json.loads(line))
    return logs


def load_logs_multi(paths: list[Path]) -> list[LogDict]:
    """複数ログファイルを読み込み、時系列でソートして返す"""
    logs: list[LogDict] = []
    for p in paths:
        logs.extend(load_logs(p))

    # 🔥 時系列ソート
    logs.sort(key=lambda x: str(x.get("time", "")))
    return logs


# =========================
# 検出系
# =========================
def detect_trace_jumps(logs: list[LogDict]) -> list[LogDict]:
    """trace_idの変化を検出する"""
    results: list[LogDict] = []
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

        prev = current

    return results


def detect_errors(logs: list[LogDict]) -> list[LogDict]:
    """ERROR/CRITICALレベルのログを検出する"""
    results: list[LogDict] = []

    for log in logs:
        if log.get("level") in ("ERROR", "CRITICAL"):
            message: str | None = log.get("what", {}).get("message", "")
            if not isinstance(message, str):
                message = ""

            results.append(
                _build_event(
                    log,
                    log.get("level", "ERROR"),
                    message,
                )
            )

    return results


def detect_reboot(logs: list[LogDict]) -> list[LogDict]:
    """再起動検出（system_reboot_detectedイベント）"""
    results: list[LogDict] = []

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


def detect_repeat_errors(logs: list[LogDict]) -> list[LogDict]:
    """同一エラーメッセージの繰り返しを検出する"""
    results: list[LogDict] = []
    seen: set[str] = set()

    for log in logs:
        message: str | None = log.get("what", {}).get("message")

        if not isinstance(message, str):
            continue

        if message in seen:
            results.append(
                _build_event(
                    log,
                    "REPEAT_ERROR",
                    f"repeated error: {message}",
                )
            )
        else:
            seen.add(message)

    return results


# =========================
# 要約
# =========================
def summarize(logs: list[LogDict]) -> list[LogDict]:
    """ログから重要イベントを抽出して要約する"""
    results: list[LogDict] = []

    results.extend(detect_trace_jumps(logs))
    results.extend(detect_errors(logs))
    results.extend(detect_reboot(logs))
    results.extend(detect_repeat_errors(logs))

    return sorted(results, key=lambda x: str(x.get("time", "")))


# =========================
# イベント変換
# =========================
def _build_event(
    log: LogDict,
    type_: str,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> LogDict:
    type_ = log.get("type") or log.get("level") or "INFO"
    message = log.get("message") or log.get("what", {}).get("message", "")
    return {
        "time": log.get("time"),
        "type": type_,
        "trace_id": log.get("trace_id"),
        "message": message,
        "data": data or {},
        "raw": log,
    }
