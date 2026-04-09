# -*- coding: utf-8 -*-
"""Logger + Monitor + Searcher の統合テスト
「E2Eテスト（統合テスト）」"""
#########################
# Author: F.Kurokawa
# Description:
# Loggerの連携テスト用
#########################
from __future__ import annotations

from pathlib import Path
import time
from typing import Any, TYPE_CHECKING

from env_paths import LOGS_DIR
from logs.log_app import get_logger
from logs.system_monitor import SystemMonitor
from logs.log_searcher import load_logs, summarize


LOG_DIR: Path = LOGS_DIR

if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger

def run_test() -> None:
    """連動テスト実行関数"""
    print("=== TEST START ===")

    logger: "AppLogger" = get_logger()
    monitor: SystemMonitor = SystemMonitor(logger)
    # 疑似動作
    for _ in range(5):
        monitor.tick()
        time.sleep(1.1)  # clock jump を誘発させるために1.1秒待つ
    logger.error("test_error", context={"test": True})
    logger.info("test_info", context={"value": 123})
    logger.warning("test_warning", context={"warning_level": "high"})
    logger.critical("test_critical", context={"critical": True})
    monitor.force_reboot_test()
    monitor.tick()
    logger.info("test_info_2", context={"message": "The logger is working perfectly."})

    print("ログ生成完了")


    log_files: list[Path] = list(LOG_DIR.glob("*.log"))
    if not log_files:
        print("ログファイルがありません")
        return

    # 最新ログ取得
    latest: Path = max(log_files, key=lambda p: p.stat().st_mtime)

    print(f"使用ログ: {latest}")

    logs: list[dict[str, Any]] = load_logs(latest)
    events: list[dict[str, Any]] = summarize(logs)

    print("\n=== EVENTS ===")
    for e in events:
        print(f"{e['type']:12} | {e['message']:25} | {e.get('time')}")

    print("\n=== TEST END ===")


if __name__ == "__main__":
    run_test()
