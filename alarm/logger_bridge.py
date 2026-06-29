# -*- coding: utf-8 -*-
# pylint: disable=W2301
"""alarm 用 logger 取得ブリッジ。"""

from __future__ import annotations

from importlib import import_module
from pprint import pformat
from pathlib import Path
from datetime import datetime
from types import ModuleType
from typing import Any, Protocol, runtime_checkable, cast


@runtime_checkable
class AlarmLogger(Protocol):
    """alarm 側で必要とする最小 logger プロトコル。"""

    def debug(self, message: str, **kwargs: Any) -> None:
        """デバッグログ出力。"""
        ...
    def info(self, message: str, **kwargs: Any) -> None:
        """情報ログ出力。"""
        ...
    def warning(self, message: str, **kwargs: Any) -> None:
        """警告ログ出力。"""
        ...
    def error(self, message: str, **kwargs: Any) -> None:
        """エラーログ出力。"""
        ...
    def critical(self, message: str, **kwargs: Any) -> None:
        """重大ログ出力。"""
        ...


class FallbackLogger:
    """外部 Logger_Project が無い場合の簡易 logger。"""

    def __init__(self, name: str = "alarm") -> None:
        self.name: str = name
        self.log_dir: Path = Path.cwd() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file: Path = self.log_dir / f"{self.name}_fallback.log"

    def _emit(self, level: str, message: str, **kwargs: Any) -> None:
        """ログ出力。context があれば付加する。"""
        context: Any | None = kwargs.get("context")
        suffix: str = ""
        if context:
            suffix = f" | context={pformat(context, compact=True)}"

        line: str = (
            f"{datetime.now().isoformat(timespec='seconds')} "
            f"[{level}] [{self.name}] {message}{suffix}"
        )

        print(line)

        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            # fallback の fallback なので、ここでは落とさない
            pass

    def debug(self, message: str, **kwargs: Any) -> None:
        """デバッグログ出力。"""
        self._emit("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """情報ログ出力。"""
        self._emit("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """警告ログ出力。"""
        self._emit("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """エラーログ出力。"""
        self._emit("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """重大ログ出力。"""
        self._emit("CRITICAL", message, **kwargs)


def _load_external_logger(name: str) -> AlarmLogger | None:
    """Logger_Project があれば取得し、無ければ None を返す。"""

    try:
        module: ModuleType = import_module("logs.multi_info_logger")
    except ModuleNotFoundError:
        return None

    # 1. get_logger があれば使う
    get_logger_attr: Any | None = getattr(module, "get_logger", None)
    if callable(get_logger_attr):
        try:
            candidate: object = get_logger_attr(name)
        except TypeError:
            candidate = get_logger_attr()
        except Exception as e: # pylint: disable=broad-exception-caught
            # debug 用に print しておく。logger が無い場合は、ここで落ちるとログが残らないので。
            print(f"[警告] 外部 logger 取得に失敗しました: {e}")
            candidate = None

        if candidate is not None and _looks_like_alarm_logger(candidate):
            return cast(AlarmLogger, candidate)

    # 2. get_logger が無ければ AppLogger を使う
    app_logger_class: Any | None = getattr(module, "AppLogger", None)
    if app_logger_class is None:
        return None

    try:
        # AppLogger は name ではなく、引数なしで生成する
        candidate = app_logger_class()
    except Exception as e: # pylint: disable=broad-exception-caught
        # debug 用に print しておく。logger が無い場合は、ここで落ちるとログが残らないので。
        print(f"[警告] 外部 logger 取得に失敗しました: {e}")
        return None

    if _looks_like_alarm_logger(candidate):
        return cast(AlarmLogger, candidate)

    return None


def _looks_like_alarm_logger(candidate: object) -> bool:
    """alarm が必要とする logger メソッドを持っているか確認する。"""
    required_methods = ("debug", "info", "warning", "error", "critical")
    return all(
        callable(getattr(candidate, method_name, None))
        for method_name in required_methods
    )


def get_alarm_logger() -> AlarmLogger:
    """alarm 用 logger を返す。外部依存が無ければ簡易 logger を返す。"""

    logger: AlarmLogger | None = _load_external_logger("alarm")
    if logger is not None:
        return logger
    return FallbackLogger("alarm")
