# -*- coding: utf-8 -*-
"""アラームログ記録ユーティリティモジュール"""
#########################
# Author: F.Kurokawa
# Description:
# アラーム関連のログを記録するユーティリティクラスを提供する。
#########################

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypedDict, cast


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


class AlarmLogger:
    """簡易ログ記録ユーティリティ"""

    def __init__(self, log_dir: Path) -> None:
        self.log_dir: Path = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file: Path = self.log_dir / "alarm.log"

    # ------------------------------
    # 内部共通処理
    # ------------------------------
    def _json_safe(self, obj: Any) -> Any:
        """JSONに書けない型を安全に変換する"""
        if isinstance(obj, datetime):
            return obj.isoformat()
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
    ) -> None:
        """ログ記録の共通処理"""
        safe_alarm_id: str = alarm_id if alarm_id else "UNASSIGNED"

        _json_safe: Callable[..., Any] = self._json_safe
        record: LogRecord = {
            "level": level,
            "time": (timestamp or datetime.now()).isoformat(),
            "where": where,
            "what": {
                "message": message,
                "alarm_id": safe_alarm_id,
            },
            "context": context or {},
        }

        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(_json_safe(record), ensure_ascii=False) + "\n")
                f.flush()
        except (OSError, IOError, json.JSONDecodeError) as e:
        # ログ失敗ではアプリを止めない
            print("[Logger Error]", e)

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
    ) -> None:
        """情報ログ（通常の状態遷移・自動補完など）"""
        self._write(
            level="INFO",
            message=message,
            where=where,
            alarm_id=alarm_id,
            context=context,
            timestamp=timestamp,
        )

    def warning(
        self,
        message: str,
        where: LogWhere,
        alarm_id: str | None = None,
        context: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """警告ログ（鳴る可能性があったが抑制した等）"""
        self._write(
            level="WARNING",
            message=message,
            where=where,
            alarm_id=alarm_id,
            context=context,
            timestamp=timestamp,
        )

    def error(
        self,
        message: str,
        where: LogWhere,
        alarm_id: str | None = None,
        context: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        """エラーログ（設計的に想定外の状態）"""
        self._write(
            level="ERROR",
            message=message,
            where=where,
            alarm_id=alarm_id,
            context=context,
            timestamp=timestamp,
        )

    def has_errors(self) -> bool:
        """エラーログが存在するかどうかを返す"""
        try:
            with self.log_file.open("r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line)
                    if record.get("level") == "ERROR":
                        return True
        except (OSError, IOError, json.JSONDecodeError):
            # ログファイルが読めない場合はエラーがあるとみなす
            return True
        return False

# EOF
