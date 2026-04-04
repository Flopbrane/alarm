# -*- coding: utf-8 -*-
"""汎用JSONロガーモジュール

どのプロジェクトでも使える汎用ロガー。
1行1JSON（JSON Lines）形式でログを保存する。

主な機能:
- コンソール / ファイル / 両方 出力
- 日付変更時のログファイル自動切替
- trace_id による処理追跡
- 呼び出し元情報(where)の自動取得
- datetime / Path / Enum / set / tuple などのJSON安全化
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
import uuid
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from types import CodeType, FrameType
from typing import Any, TypedDict, cast, Iterable


# ==========================================================
# 型
# ==========================================================
class LogOutput(Enum):
    """出力先の指定"""
    CONSOLE = "console"
    FILE = "file"
    BOTH = "both"


class LogLevel(Enum):
    """ログレベルの指定"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    REBOOT = "REBOOT"  # 特殊レベル（再起動ログ用）


class LogWhere(TypedDict, total=False):
    """ログの発生箇所情報"""
    line: int
    module: str
    file: str
    function: str


class LogWhat(TypedDict, total=False):
    """ログの内容情報"""
    message: str
    action: str
    status: str
    category: str


class LogRecord(TypedDict):
    """ログレコードの情報"""
    level: LogLevel
    time: datetime | str
    trace_id: str | None
    where: LogWhere
    what: LogWhat
    context: dict[str, Any]
    output: str


# ==========================================================
# Multi-Logger
# ==========================================================
class AppLogger:
    """アプリケーション用ロガークラス"""
    _TRACE_ID_VAR: ContextVar[str | None] = ContextVar("trace_id", default=None)

    def __init__(
        self,
        log_dir: Path,
        *,
        app_name: str = "app",
        default_output: LogOutput = LogOutput.BOTH,
    ) -> None:
        self.log_dir: Path = log_dir
        self.app_name: str = app_name
        self.default_output: LogOutput = default_output

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file: Path = self._get_log_file()
        self.log_file.touch(exist_ok=True)
        self._new_trace_id()

    # ==========================================================
    # trace_id 管理
    # ==========================================================
    def _new_trace_id(self) -> str:
        """新しい trace_id を生成してセットする"""
        trace_id = str(uuid.uuid4())
        self._TRACE_ID_VAR.set(trace_id)
        return trace_id

    def _get_trace_id(self) -> str | None:
        """現在の trace_id を取得する"""
        return self._TRACE_ID_VAR.get()

    # -----------------------------
    # ファイル管理
    # -----------------------------
    def _get_log_file(self) -> Path:
        """現在のログファイルパスを取得する"""
        today: str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"{self.app_name}_{today}.log"

    def _ensure_file(self) -> None:
        current: Path = self._get_log_file()
        if current != self.log_file:
            self.log_file = current
            self.log_file.touch(exist_ok=True)

    # -----------------------------
    # where（自動取得）
    # -----------------------------
    def get_where_auto(self) -> LogWhere:
        """呼び出し元情報を自動で取得する"""
        frame: FrameType | None = inspect.currentframe()

        try:
            for _ in range(10):
                if frame is None:
                    break

                code: CodeType = frame.f_code
                filename: str = code.co_filename

                if filename != __file__:
                    return {
                        "line": frame.f_lineno,
                        "module": filename,
                        "file": filename,
                        "function": code.co_name,
                    }

                frame = frame.f_back

            return {
                "line": -1,
                "module": "",
                "file": "",
                "function": "",
            }

        finally:
            del frame  # 循環参照防止のためにフレームを削除

    def where(self) -> LogWhere:
        """旧実装互換の呼び出し元取得エイリアス"""
        return self.get_where_auto()
    # -----------------------------
    # JSON安全化
    # -----------------------------
    def _safe(self, obj: Any) -> Any:
        """JSON記述用変換関数"""
        if obj is None:
            return None

        if isinstance(obj, (str, int, float, bool)):
            return obj

        if isinstance(obj, datetime):
            return obj.replace(microsecond=0).isoformat()

        if isinstance(obj, date):
            return obj.isoformat()

        if isinstance(obj, time):
            return obj.replace(microsecond=0).isoformat()

        if isinstance(obj, Path):
            return str(obj)

        if isinstance(obj, Enum):
            return obj.value

        if is_dataclass(obj) and not isinstance(obj, type):
            return self._safe(asdict(obj))

        if isinstance(obj, dict):
            obj_dict: dict[Any, Any] = cast(dict[Any, Any], obj)
            return {str(k): self._safe(v) for k, v in obj_dict.items()}

        if isinstance(obj, (list, tuple, set)):
            iterable: Iterable[Any] = cast(Iterable[Any], obj)
            return [self._safe(v) for v in iterable]

        return str(obj)

    # -----------------------------
    # 書き込み
    # -----------------------------
    def _log(
        self,
        level: LogLevel,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        output: LogOutput | None = None,
        where: LogWhere | None = None,
        alarm_id: str | None = None,
        timestamp: datetime | str | None = None,
        trace_id: str | None = None,
        action: str | None = None,
        status: str | None = None,
        category: str | None = None,
    ) -> None:
        """ログを記録する。

        旧来の呼び出し側が渡している where / alarm_id / timestamp も
        受け取って後方互換を維持する。
        """
        self._ensure_file()

        resolved_context: dict[str, Any] = dict(context or {})
        if alarm_id is not None:
            resolved_context.setdefault("alarm_id", alarm_id)

        what: LogWhat = {"message": message}
        if action is not None:
            what["action"] = action
        if status is not None:
            what["status"] = status
        if category is not None:
            what["category"] = category

        record: LogRecord = {
            "level": level,
            "time": timestamp or datetime.now().replace(second=0,microsecond=0),
            "trace_id": trace_id if trace_id is not None else self._get_trace_id(),
            "where": where or self.get_where_auto(),
            "what": what,
            "context": resolved_context,
            "output": (output or self.default_output).value,
        }

        safe: dict[str, Any] = self._safe(record)

        # console
        if (output or self.default_output) in (LogOutput.CONSOLE, LogOutput.BOTH):
            trace: str | None = safe.get("trace_id")
            if trace:
                print(f"[{level.value}] [{trace}] {message}")
            else:
                print(f"[{level.value}] {message}")

        # file
        if (output or self.default_output) in (LogOutput.FILE, LogOutput.BOTH):
            try:
                with self.log_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(safe, ensure_ascii=False) + "\n")
            except Exception as e: # pylint: disable=broad-exception-caught
                print(f"[LOGGER ERROR] {e}")
            # pylint: enable=broad-exception-caught
    # -----------------------------
    # -----------------------------
    # public API
    # -----------------------------
    # ここにログレベルごとのメソッドを定義
    # -----------------------------
    def debug(self, message: str, **kw: Any) -> None:
        """デバッグレベルのログを記録する"""
        self._log(LogLevel.DEBUG, message, **kw)

    def info(self, message: str, **kw: Any) -> None:
        """情報レベルのログを記録する"""
        self._log(LogLevel.INFO, message, **kw)

    def warning(self, message: str, **kw: Any) -> None:
        """警告レベルのログを記録する"""
        self._log(LogLevel.WARNING, message, **kw)

    def error(self, message: str, **kw: Any) -> None:
        """エラーレベルのログを記録する"""
        self._log(LogLevel.ERROR, message, **kw)

    def critical(self, message: str, **kw: Any) -> None:
        """クリティカルレベルのログを記録する"""
        self._log(LogLevel.CRITICAL, message, **kw)

    def set_trace_id(self, trace_id: str) -> None:
        """外部から trace_id をセットするためのメソッド"""
        self._TRACE_ID_VAR.set(trace_id)
        self._log(LogLevel.REBOOT, f"Trace ID set to {trace_id}", output=LogOutput.BOTH)
