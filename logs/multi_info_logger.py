# -*- coding: utf-8 -*-
#########################
# Author: F.Kurokawa
# Description:
# AppLoggerは、アプリケーション全体で使用するためのシングルトンロガークラスです。
#########################
# log_searcher.py
"""汎用JSONロガーモジュール

どのプロジェクトでも使える汎用ロガー。
1行1JSON（JSON Lines）形式でログを保存する。

主な機能・注意事項:
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
＜要注意事項＞
- ★★ Logger内部は「純粋関数的に振る舞うこと」
  （副作用としてのLogger内部のログ出力を持たないこと）
  特に以下のメソッド内では、絶対に logger.debug/info/warning などを呼び出してはならない：

    ・_log（ログ生成の司令塔）
    ・_build_log_record（ログデータ構築）
    ・_safe（JSON変換処理）
    ・_emit（出力処理）

  これらの内部処理中にログを出力すると、ログ処理が再帰的に呼び出され、
  無限ループやスタックオーバーフローを引き起こす危険がある。

- 内部処理中の警告や異常は、loggerを使用せず、
  print() または専用の内部出力関数で処理すること。

- Loggerは「事実を記録するための装置」であり、
  Logger内部の処理状態を記録するものではないことを意識すること。"""
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
from typing import Any, cast, Iterable
from logs.log_paths import LOGS_DIR  # ← ここ重要
from logs.log_types import ISODateTimeStr, RawLogRecord # ← ここ重要
from logs.time_utils import (
    now_utc,
    to_utc_datetime,
    to_utc_iso, # ← ここ重要
    DateLike,
    )
from logs.log_types import LogLevel, LogOutput, LogWhere, LogWhat
from logs.logger_config import LoggerConfig

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
    _time: ISODateTimeStr = ISODateTimeStr(
        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        )

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
        config: LoggerConfig | None = None,
    ) -> None:
        # 初期化は一度だけ行う（シングルトンのため）
        if self._initialized:
            return

        self.log_dir: Path = log_dir
        self.app_name: str = app_name
        self.default_output: LogOutput = default_output
        # 🔥 修正ここ
        self.config: LoggerConfig = config or LoggerConfig()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        today_utc: date = now_utc().date()
        self.log_file: Path = self._get_log_file(today_utc)
        self.log_file.touch(exist_ok=True)
        self.new_trace_id()
        self._initialized = True # 🔥 これ必須
        self._current_date: ISODateTimeStr = today_utc.isoformat()  # 🔥 これ追加

    @classmethod
    def reset_instance(cls) -> None:
        """ロガーのインスタンスをリセットする（テスト用）"""
        cls._instance = None

    def now(self) -> datetime:
        """現在時刻の設定"""
        dt: datetime = datetime.now(timezone.utc)

        if self.config.time_precision == "second":
            return dt.replace(microsecond=0)

        return dt

    # ==========================================================
    # trace_id 管理
    # ==========================================================
    def new_trace_id(self) -> str:
        """新しい trace_id を生成してセットする"""
        trace_id: str = uuid.uuid4().hex
        self._TRACE_ID_VAR.set(trace_id)
        return trace_id

    def get_trace_id(self) -> str:
        """現在の trace_id を取得する"""
        trace_id: str | None = self._TRACE_ID_VAR.get()
        if trace_id is None:
            trace_id = self.new_trace_id()
        return trace_id

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
        now: datetime = now_utc()
        today_str: ISODateTimeStr = now.strftime("%Y-%m-%d")

        if hasattr(self, "_current_date") and self._current_date == today_str:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self._get_log_file(now.date())
        self._current_date = today_str

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
                        "file": filename,
                        "line": frame.f_lineno,
                        "function": code.co_name,
                        "module": filename,
                    }

                frame = frame.f_back

            return {
                "file": "",
                "line": -1,
                "function": "",
                "module": "",
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
        timestamp: DateLike,
        alarm_id: str | None,
        action: str | None,
        status: str | None,
        category: str | None,
        context: dict[str, Any] | None,
        where: LogWhere | None,
        output: LogOutput | None,
    ) -> RawLogRecord:
        """ログレコードを構築する（内部使用）"""
        # -----------------------------
        # context
        # -----------------------------
        resolved_context: dict[str, Any] = dict(context or {})
        if alarm_id is not None:
            resolved_context.setdefault("alarm_id", alarm_id)

        # -----------------------------
        # time（完全保証）
        # -----------------------------
        timestamp_utc: str = (
            to_utc_iso(timestamp)
            or to_utc_iso(now_utc())
            or now_utc().isoformat()
        )

        # -----------------------------
        # what
        # -----------------------------
        what: LogWhat = {"message": message}

        if action is not None:
            what["action"] = action
        if status is not None:
            what["status"] = status
        if category is not None:
            what["category"] = category

        # -----------------------------
        # where
        # -----------------------------
        resolved_where: LogWhere = where or self.get_where_auto()

        # -----------------------------
        # trace_id
        # -----------------------------
        resolved_trace_id: str = trace_id or self.get_trace_id()
        if not resolved_trace_id:
            resolved_trace_id = self.get_trace_id() # 絶対に trace_id を空にしない！
        # -----------------------------
        # output
        # -----------------------------
        resolved_output: str = (output or self.default_output).value

        # -----------------------------
        # 最終構築（完全一致）
        # -----------------------------
        record: RawLogRecord = {
            "level": level.value,
            "time": timestamp_utc,
            "trace_id": resolved_trace_id,
            "where": resolved_where,
            "what": what,
            "context": resolved_context,
            "output": resolved_output,
        }

        return record
    # -----------------------------
    # メイン（司令塔）
    # -----------------------------
    def _log(
        self,
        level: LogLevel,
        message: str,
        *,
        trace_id: str | None = None,
        timestamp: DateLike = None,
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
        timestamp_utc: ISODateTimeStr = (
            to_utc_iso(timestamp) or
            to_utc_iso(now_utc()) or
            ISODateTimeStr(now_utc().isoformat())
        )
        record: RawLogRecord = self._build_log_record(
            level,
            message=message,
            trace_id=trace_id,
            timestamp=timestamp_utc,
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
            obj_utc: datetime | None = to_utc_datetime(obj)
            return obj_utc.isoformat() if obj_utc else datetime.now(timezone.utc).isoformat()

        if isinstance(obj, date):
            obj_utc = to_utc_datetime(obj)
            return obj_utc.isoformat() if obj_utc else None

        if isinstance(obj, time):
            print("[LOGGER WARNING] time単体はサポートされていません")
            return None

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
    def _emit(self, record: RawLogRecord) -> None:
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
