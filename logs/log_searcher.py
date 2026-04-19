# -*- coding: utf-8 -*-
"""ログ検索・分析機能（型安全版）"""
from __future__ import annotations

import re
from datetime import date, timezone, datetime
from pathlib import Path
from typing import Any, TYPE_CHECKING
from logs.log_storage import load_log
from logs.log_types import LogDict, Event, TraceId, EventType, LogLevel
from logs.log_validator import validate_log
from logs.log_app import get_logger


if TYPE_CHECKING:
    from multi_info_logger import AppLogger


#########################
# Author: F.Kurokawa
# Description:
# logファイルを読み込み、重要ポイントを抽出する
#########################
# LogDict → 記録
# Event → 意味
# | 層         | 型                     |
# | ---------- | ---------------------- |
# | Logger出力 | RawLogRecord（やや緩い）|
# | validate後 | LogDict（完全）        |
# | 分析後     | Event（意味付き）       |


# =========================
# 日付抽出（YYYY-MM-DD）
# =========================
DATE_PATTERN: re.Pattern[str] = re.compile(r"\d{4}-\d{2}-\d{2}")

def get_logger_safe() -> "AppLogger":
    """初期インスタンス化回避"""
    logger:"AppLogger" = get_logger()
    return logger

def extract_date_from_path(p: Path) -> date | None:
    """ファイルネームから日付を取り出す"""
    match: re.Match[str] | None = DATE_PATTERN.search(p.stem)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group())
    except ValueError:
        return None


# =========================
# ログファイル取得
# =========================
def get_log_files(
    log_dir: Path,
    start: date | None = None,
    end: date | None = None,
) -> list[Path]:
    """ログファイルから内容を抽出する"""
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
# ==========================
# 重要イベントを抽出する(全体の入口)
# ==========================
def search_logs(
    log_dir: Path,
    start: date | None = None,
    end: date | None = None,
) -> list[Event]:
    """ログファイルを読み込み、重要イベントを抽出する入口関数"""
    paths: list[Path] = get_log_files(log_dir, start, end)
    logs: list[LogDict] = collect_logs(paths)
    return summarize(logs)


# =========================
# ログ収集（型確定ゾーン🔥）
# =========================
def collect_logs(paths: list[Path]) -> list[LogDict]:
    """複数のLogファイルからLogを集積する。"""
    logs: list[LogDict] = []
    logger: "AppLogger" = get_logger_safe()

    for p in paths:
        raw_logs: list[dict[str, Any]] = load_log(p)  # list[dict]
        for raw in raw_logs:
            valid_raw: LogDict | None = validate_log(raw, logger)
            if valid_raw is not None:
                logs.append(valid_raw)

    logs.sort(key=lambda x: x["time"])
    return logs


# =========================
# イベント生成
# =========================
def _build_event(
    log: LogDict,
    type_: EventType | None,
    message: str,
    *,
    data: dict[str, Any] | None = None,
) -> Event:
    """Logから出力されたイベントを整理する
    _build_event(
        log: LogDict,
        type_: str,
        message: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> Event:
    """
    detected_at: str = datetime.now(timezone.utc).isoformat(timespec="seconds")
    level_str: str = str(log.get("level", "INFO")).upper()

    try:
        level = LogLevel(level_str)
    except ValueError:
        level: LogLevel = LogLevel.INFO

    return Event(
        type=type_,
        level=level,  # ←🔥
        time=log["time"],
        detected_at=detected_at,  # ←追加🔥
        trace_id=TraceId(log["trace_id"]),  # ← ここ🔥
        message=message,
        data=data or {},
        raw=log,
    )

# =========================
# 検出系（Log → Event）
# =========================
def detect_trace_jumps(logs: list[LogDict]) -> list[Event]:
    """
    ★trace_idの変化を検出する
    - trace_idが変わる = 実行セッションが切り替わったことを意味する
    - 再起動、プロセス再生成、ログ再初期化などを検出可能
    """
    results: list[Event] = []
    prev: str | None = None

    for row in logs:

        current: str = row["trace_id"]

        if prev is not None and current != prev:
            results.append(
                _build_event(
                    row,
                    EventType.TRACE_JUMP,
                    "trace_id changed",
                    data={"from": prev, "to": current},
                )
            )

        prev = current

    return results


def detect_errors(logs: list[LogDict]) -> list[Event]:
    """LogファイルからのError検出"""
    results: list[Event] = []

    for log in logs:
        level: str = log["level"]
        message: str = log["what"]["message"]

        if level == "ERROR":
            results.append(
                _build_event(
                    log,
                    EventType.ERROR,
                    message,
                )
            )

        elif level == "CRITICAL":
            results.append(
                _build_event(
                    log,
                    EventType.CRITICAL,
                    message,
                )
            )

    return results


def detect_reboot(logs: list[LogDict]) -> list[Event]:
    """再起動の検出(WindowsUpdateが走った可能性があるので)"""
    results: list[Event] = []

    for log in logs:
        if log["what"]["message"] == "system_reboot_detected":
            results.append(
                _build_event(
                    log,
                    EventType.REBOOT,
                    "system reboot detected",
                )
            )

    return results


def detect_repeat_errors(events: list[Event]) -> list[Event]:
    """
    ★同一エラーメッセージの繰り返しを検出する（異常パターン検出）
    - message単位で重複を検出
    - 同一原因の再発（無限ループ・リトライ失敗）を特定
    - context情報により再現条件の分析が可能
    """
    results: list[Event] = []
    seen: set[str] = set()

    for e in events:

        # 🔥 エラー系だけ対象
        if e.type not in (EventType.ERROR, EventType.REPEAT_ERROR):
            continue

        message: str = e.message

        if message in seen:
            results.append(
                _build_event(
                    e.raw,
                    EventType.REPEAT_ERROR,
                    f"repeated error: {message}",
                )
            )
        else:
            seen.add(message)

    return results


def build_normal_events(logs: list[LogDict]) -> list[Event]:
    """INFO専用のEvent変換関数"""
    results: list[Event] = []
    # 🔥 通常ログ追加（これが重要）
    for log in logs:
        results.append(
            _build_event(
                log,
                type_=None,
                message=log.get("what", {}).get("message", "")
            )
        )
    return results

# =========================
# 要約（統合レイヤー）
# =========================
# 🚀【まとめ】
# 👉 "INFO"をtypeに入れる → ❌
# 👉 typeは分析専用 → ⭕
# 👉 Noneを許可する → 必須
def summarize(logs: list[LogDict]) -> list[Event]:
    """ 分析結果の統合処理 """
    # 🔥 ① まず時系列ソート
    logs = sorted(logs, key=lambda x: x["time"])

    base_events: list[Event] = build_normal_events(logs)

    results: list[Event] = []
    results.extend(base_events)

    results.extend(detect_trace_jumps(logs))
    results.extend(detect_errors(logs))
    results.extend(detect_reboot(logs))

    # 🔥 ② 時系列保証された状態で判定
    results.extend(detect_repeat_errors(base_events))

    return sorted(results, key=lambda x: x.time)
