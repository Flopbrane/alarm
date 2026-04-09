# -*- coding: utf-8 -*-
"""汎用JSONロガーモジュール

どのプロジェクトでも使える汎用ロガー。
1行1JSON（JSON Lines）形式でログを保存する。

主な機能:
- コンソール / ファイル / 両方 出力
- 日付変更時のログファイル自動切替
- trace_id による処理追跡(trace_idはプログラム起動に対して一意のIDです。)
- 呼び出し元情報(where)の自動取得
- datetime / Path / Enum / set / tuple などのJSON安全化
- Whereの自動取得は、ログ呼び出し元のスタックフレームを遡って、最初に見つかったユーザコードの位置を特定することで実現している。
- ロガーはシングルトンとして実装されており、アプリケーション全体で同じインスタンスが共有される。
- ロガーのインスタンスは、テストなどでリセット可能。
- ログレコードは、レベル、タイムスタンプ、trace_id、where、what、context、outputの情報を持つ。
- ログレコードは、JSON Lines形式でファイルに保存されるとともに、コンソールにも出力される。
- ログレベルごとに専用のメソッド(debug/info/warning/error/critical)が用意されている。
- ログの内容(what)は、messageを必須とし、action/status/categoryを任意で含むことができる。
- ログの発生箇所(where)は、line/module/file/functionの情報を含む。
"""
from __future__ import annotations

import inspect
import json
import uuid
import warnings
from contextvars import ContextVar
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time, timezone
from enum import Enum
from pathlib import Path
from types import CodeType, FrameType
from typing import Any, TypedDict, cast, Iterable, TypeAlias
from env_paths import LOGS_DIR  # ← ここ重要
# pylint: disable=too-many-instance-attributes, too-many-arguments, too-few-public-methods
ISODateTimeStr: TypeAlias = str  # ISOフォーマットの日時文字列

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

# LogRecord = イミュータブル（変更しない前提）なので TypedDict で定義
class LogRecord(TypedDict, total=False):
    """ログレコードの情報"""
    level: LogLevel
    time: datetime | ISODateTimeStr
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

    # Singleton 実装/クラス変数
    _instance: "AppLogger | None" = None
    _TRACE_ID_VAR: ContextVar[str | None] = ContextVar("trace_id", default=None)
    # 🔥 これ追加
    _initialized: bool = False
    _time: ISODateTimeStr = ISODateTimeStr(datetime.now(timezone.utc).isoformat())
    # シングルトン実装
    def __new__(cls, *args: Any, **kwargs: Any) -> "AppLogger":
        """シングルトン実装"""
        if cls._instance is not None:
            warnings.warn(
                "AppLogger is a singleton. Use get_logger() instead.",
                RuntimeWarning,
                stacklevel=2,
            )
            return cls._instance

        instance: "AppLogger" = super().__new__(cls)
        cls._instance = instance
        return instance

    # 初期化
    def __init__(
        self,
        log_dir: Path = LOGS_DIR,
        *,
        app_name: str = "app",
        default_output: LogOutput = LogOutput.BOTH,
    ) -> None:
        # 初期化は一度だけ行う（シングルトンのため）
        if self._initialized:
            return

        self.log_dir: Path = log_dir
        self.app_name: str = app_name
        self.default_output: LogOutput = default_output

        self.log_dir.mkdir(parents=True, exist_ok=True)
        today: date = date.today()
        self.log_file: Path = self._get_log_file(today)
        self.log_file.touch(exist_ok=True)
        self.new_trace_id()
        self._initialized = True # 🔥 これ必須

    @classmethod
    def reset_instance(cls) -> None:
        """ロガーのインスタンスをリセットする（テスト用）"""
        cls._instance = None

    # ==========================================================
    # trace_id 管理
    # ==========================================================
    def new_trace_id(self) -> str:
        """新しい trace_id を生成してセットする"""
        trace_id = str(uuid.uuid4())
        self._TRACE_ID_VAR.set(trace_id)
        return trace_id

    def get_trace_id(self) -> str | None:
        """現在の trace_id を取得する"""
        return self._TRACE_ID_VAR.get()

    # -----------------------------
    # ファイル管理
    # -----------------------------
    def _build_log_filename(self, dt: date) -> str:
        """ログファイル名を生成する（単一責務）"""
        return f"{self.app_name}_{dt.isoformat()}.jsonl"


    def _get_log_file(self, dt: date) -> Path:
        """現在のログファイルパスを取得する"""
        return self.log_dir / self._build_log_filename(dt)

    def _ensure_file(self) -> None:
        """ログファイルを準備（なければ作成）"""

        if hasattr(self, "log_file"):
            return

        now: datetime = datetime.now()

        # 例: log_2026-04-07_14-30-00.jsonl
        filename: str = now.strftime("log_%Y-%m-%d.jsonl")

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        self.log_file = log_dir / filename

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
    # ログの生成
    # -----------------------------
    def _build_log_record(
        self,
        level: LogLevel,
        message: str,
        *,
        trace_id: str | None,
        timestamp: datetime | str | None,
        alarm_id: str | None,
        action: str | None,
        status: str | None,
        category: str | None,
        context: dict[str, Any] | None,
        where: LogWhere | None,
        output: LogOutput | None,
    ) -> LogRecord:
        """ログレコードを構築する（内部使用）"""
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

        return {
            "level": level,
            "time": timestamp or datetime.now().replace(second=0, microsecond=0),
            "trace_id": trace_id if trace_id is not None else self.get_trace_id(),
            "where": where or self.get_where_auto(),
            "what": what,
            "context": resolved_context,
            "output": (output or self.default_output).value,
        }

    # -----------------------------
    # メイン（司令塔）
    # -----------------------------
    def _log(
        self,
        level: LogLevel,
        message: str,
        *,
        trace_id: str | None = None,
        timestamp: datetime | str | None = None,
        alarm_id: str | None = None,
        action: str | None = None,
        status: str | None = None,
        category: str | None = None,
        context: dict[str, Any] | None = None,
        where: LogWhere | None = None,
        output: LogOutput | None = None,
    ) -> None:
        """ログ記録制御（内部使用）

        ★★ ログレコード（LogRecord）を生成し、出力（console/file）を行う司令塔関数

        ・事実（fact）をそのまま記録する層
        ・ログの生成責務のみを持つ（分析は行わない）
        """

        self._ensure_file()

        record: LogRecord = self._build_log_record(
            level,
            message=message,
            trace_id=trace_id,
            timestamp=timestamp,
            alarm_id=alarm_id,
            action=action,
            status=status,
            category=category,
            context=context,
            where=where,
            output=output,
        )

        self._emit(record)
    # pylint: enable=broad-exception-caught

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
    # 出力処理 (コンソールとファイル)
    # -----------------------------
    def _emit_console(self, safe: dict[str, Any]) -> None:
        level: LogLevel | None = safe.get("level")
        message: str | None = safe.get("what", {}).get("message")
        trace_id: str | None = safe.get("trace_id")

        if trace_id:
            print(f"[{level}] [{trace_id}] {message}")
        else:
            print(f"[{level}] {message}")

    def _emit_file(self, safe: dict[str, Any]) -> None:
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(safe, ensure_ascii=False) + "\n")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"[LOGGER ERROR] {e}")

    # -----------------------------
    # 出力制御
    # -----------------------------
    def _emit(self, record: LogRecord) -> None:
        """ログレコードを実際に出力する（内部使用）"""
        safe: dict[str, Any] = cast(dict[str, Any], self._safe(record))

        output_mode: str = record.get("output", LogOutput.BOTH.value)

        if output_mode in (LogOutput.CONSOLE.value, LogOutput.BOTH.value):
            self._emit_console(safe)

        if output_mode in (LogOutput.FILE.value, LogOutput.BOTH.value):
            self._emit_file(safe)

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
