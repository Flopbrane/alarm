# -*- coding: utf-8 -*-
"""旧ロガー（非推奨）
logs/multi_info_logger.py に移行済み
"""

# ⚠️ このファイルは使用しないこと
# 将来的に.deprecatedディレクトリに移す予定
#########################
# Author: F.Kurokawa
# Description:
# アラーム関連のログを記録するユーティリティクラスを提供する。
#########################

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict, cast
import inspect
from types import FrameType, CodeType

from env_paths import LOGS_DIR


class LogOutput(Enum):
    """ログ出力先"""

    CONSOLE = "console"
    FILE = "file"
    BOTH = "both"


class LogWhere(TypedDict, total=False):
    """ログ発生箇所情報"""

    line: int
    module: str
    file: str
    class_name: str
    method_name: str
    function: str


class LogWhat(TypedDict):
    """ログ内容情報"""
    id: str | None


class LogRecord(TypedDict):
    """ログ記録情報"""
    what: LogWhat
    level: str
    time: datetime
    where: LogWhere
    message: str
    context: dict[str, Any]
    output: str
    trace_id: str | None


class AlarmLogger:
    """簡易ログ記録ユーティリティ"""

    def __init__(
        self,
        log_dir: Path = LOGS_DIR,
        default_output: LogOutput = LogOutput.BOTH,
    ) -> None:
        self.log_dir: Path = log_dir
        self.default_output: LogOutput = default_output
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file: Path = self._get_log_file()
        self.log_file.touch(exist_ok=True)

    def _get_log_file(self) -> Path:
        today: str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"alarm_{today}.log"

    # ------------------------------
    # 内部共通処理
    # ------------------------------
    def _ensure_current_log_file(self) -> None:
        """日付が変わったらログファイルを更新"""
        current_file: Path = self._get_log_file()
        if current_file != self.log_file:
            self.log_file = current_file
            self.log_file.touch(exist_ok=True)

    def _json_safe(self, obj: Any) -> Any:
        """JSONに書けない型を安全に変換する"""
        if isinstance(obj, datetime):
            return obj.replace(microsecond=0).isoformat()
        if isinstance(obj, dict):
            return {k: self._json_safe(v) for k, v in cast(dict[Any, Any], obj).items()}
        if isinstance(obj, list):
            return [self._json_safe(v) for v in cast(list[Any], obj)]
        return obj

    def _write(
        self,
        level: str,
        message: str,
        where: LogWhere,
        alarm_id: str | None = None,
        context: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
        output: LogOutput | None = None,
    ) -> None:
        """ログ記録の共通処理"""
        self._ensure_current_log_file()  # ← 追加
        actual_output: LogOutput = output or self.default_output
        safe_alarm_id: str = alarm_id if alarm_id else "UNASSIGNED"

        event_time: datetime = timestamp or datetime.now()
        record: LogRecord = {
            "what": {
                "id": safe_alarm_id,
            },
            "level": level,
            "time": event_time.replace(microsecond=0),
            "where": where,
            "message": message,
            "context": context or {},
            "output": actual_output.value,
            "trace_id": None
        }

        safe_record: Any = self._json_safe(record)

        if actual_output in (LogOutput.CONSOLE, LogOutput.BOTH):
            print(f"[{level}] {message}")

        if actual_output in (LogOutput.FILE, LogOutput.BOTH):
            try:
                with self.log_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(safe_record, ensure_ascii=False) + "\n")
                    f.flush()
            except (OSError, IOError, json.JSONDecodeError) as e:
                print(f"[{level}] {message} @ {where.get('method_name')}: {e}")

    # ------------------------------
    # 公開 API
    # ------------------------------
    def info(
        self,
        message: str,
        where: LogWhere,
        alarm_id: str | None = None,
        context: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
        output: LogOutput | None = None,
    ) -> None:
        """情報ログ（通常の状態遷移・自動補完など）"""
        self._write(
            level="INFO",
            message=message,
            where=where,
            alarm_id=alarm_id,
            context=context,
            timestamp=timestamp,
            output=output,
        )

    def warning(
        self,
        message: str,
        where: LogWhere,
        alarm_id: str | None = None,
        context: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
        output: LogOutput | None = None,
    ) -> None:
        """警告ログ（鳴る可能性があったが抑制した等）"""
        self._write(
            level="WARNING",
            message=message,
            where=where,
            alarm_id=alarm_id,
            context=context,
            timestamp=timestamp,
            output=output,
        )

    def error(
        self,
        message: str,
        where: LogWhere,
        alarm_id: str | None = None,
        context: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
        output: LogOutput | None = None,
    ) -> None:
        """エラーログ（設計的に想定外の状態）"""
        self._write(
            level="ERROR",
            message=message,
            where=where,
            alarm_id=alarm_id,
            context=context,
            timestamp=timestamp,
            output=output,
        )

    def has_errors(self) -> bool:
        """エラーログが存在するかどうかを返す"""
        self._ensure_current_log_file()  # ← 追加
        try:
            with self.log_file.open("r", encoding="utf-8") as f:

                for line in f:
                    record: dict[str, Any] = json.loads(line)
                    if record.get("level") == "ERROR":
                        return True
        except (OSError, IOError, json.JSONDecodeError):
            # ログファイルが読めない場合はエラーがあるとみなす
            return True
        return False

    def where(
        self,
        class_name: str | None = None,
        method_name: str | None = None,
    ) -> LogWhere:
        """呼び出し元の位置情報を自動取得"""
        frame: FrameType | None = inspect.currentframe()
        try:
            caller: FrameType | None = frame.f_back if frame else None

            lineno: int | Any = caller.f_lineno if caller else -1
            code: CodeType | None = caller.f_code if caller else None

            return {
                "line": lineno,
                "module": code.co_filename if code else __name__,
                "file": code.co_filename if code else "",
                "class_name": class_name or "",
                "method_name": method_name or (code.co_name if code else ""),
                "function": code.co_name if code else "",
            }
        finally:
            del frame  # ← これ超重要

# EOF
