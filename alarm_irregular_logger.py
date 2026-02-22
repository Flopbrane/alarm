# -*- coding: utf-8 -*-
"""アラームログ記録ユーティリティモジュール"""
#########################
# Author: F.Kurokawa
# Description:
# アラーム関連のログを記録するユーティリティクラスを提供する。
#########################

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, TypedDict, cast

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
    message: str
    alarm_id: str | None


class LogRecord(TypedDict):
    """ログ記録フォーマット"""
    level: str
    time: str # ISOフォーマット日時文字列
    where: LogWhere
    what: LogWhat
    context: dict[str, Any]
    output: str


class AlarmLogger:
    """簡易ログ記録ユーティリティ"""

    def __init__(self) -> None:
        self.log_dir: Path = LOGS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file: Path = self._get_log_file()
        self.log_file.touch(exist_ok=True)

    def _get_log_file(self) -> Path:
        today: str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"alarm_{today}.log"

    # ------------------------------
    # 内部共通処理
    # ------------------------------
    def _json_safe(self, obj: Any) -> Any: # type: ignore #JSONに書けない型を安全に変換する
        """JSONに書けない型を安全に変換する"""
        if isinstance(obj, datetime):
            obj: datetime = obj.replace(microsecond=0)
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._json_safe(v) for k, v in cast(dict[Any, Any], obj).items()}
        elif isinstance(obj, list):
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
        output: LogOutput = LogOutput.BOTH,
    ) -> None:
        """ログ記録の共通処理"""
        safe_alarm_id: str = alarm_id if alarm_id else "UNASSIGNED"

        record: LogRecord = {
            "level": level,
            "time": (timestamp or datetime.now()).isoformat(),
            "where": where,
            "what": {
                "message": message,
                "alarm_id": safe_alarm_id,
            },
            "context": context or {},
            "output": output.value,
        }

        safe_record: Any = self._json_safe(record)

        # 🔥 コンソール出力
        if output in (LogOutput.CONSOLE, LogOutput.BOTH):
            print(f"[{level}] {message}")

        # 🔥 ファイル出力
        if output in (LogOutput.FILE, LogOutput.BOTH):
            try:
                with self._get_log_file().open("a", encoding="utf-8") as f:
                    f.write(json.dumps(safe_record, ensure_ascii=False) + "\n")
                    f.flush()
            except (OSError, IOError, json.JSONDecodeError) as e:
                print(f"[{level}] {message} @ {where.get('method_name')}: {e}")

    def where_here(self, function: str) -> LogWhere:
        """現在のログ発生箇所情報を取得"""
        return {
            "module": __name__,
            "function": function,
        }

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
        output: LogOutput = LogOutput.CONSOLE,
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
        output: LogOutput = LogOutput.BOTH,
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
        output: LogOutput = LogOutput.BOTH,
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
        try:
            with self._get_log_file().open("r", encoding="utf-8") as f:
                for line in f:
                    record: LogRecord = json.loads(line)
                    if record.get("level") == "ERROR":
                        return True
        except (OSError, IOError, json.JSONDecodeError):
            # ログファイルが読めない場合はエラーがあるとみなす
            return True
        return False

# EOF
