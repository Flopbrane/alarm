# -*- coding: utf-8 -*-
"""Logの入出力を纏めて行う"""
#########################
# Author: F.Kurokawa
# Description:
# ログの保存・読み込みを行うモジュール
#########################
from __future__ import annotations

import json
from typing import Any
from pathlib import Path

def load_log(log_path: Path) -> list[dict[str, Any]]:
    """ログファイルを読み込む"""
    log_entries: list[dict[str, Any]] = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                log_entries.append(json.loads(line))
    except Exception as e:
        print(f"Failed to load log file {log_path}: {e}")
    return log_entries

def load_multi_logs(log_paths: list[Path]) -> list[dict[str, Any]]:
    """複数のログファイルを読み込み、時系列でソートして返す"""
    all_logs: list[dict[str, Any]] = []
    for path in log_paths:
        logs: list[dict[str, Any]] = load_log(path)
        all_logs.extend(logs)

    # 🔥 時系列ソート
    all_logs.sort(key=lambda x: str(x.get("time", "")))
    return all_logs

def save_log(log_path: Path, log_entry: dict[str, Any]) -> None:
    """ログエントリをファイルに保存する"""
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Failed to save log entry to {log_path}: {e}")
