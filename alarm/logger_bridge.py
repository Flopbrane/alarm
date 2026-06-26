# -*- coding: utf-8 -*-
# pylint: disable=W2301
"""alarm 用 logger 取得ブリッジ。"""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pprint import pformat
from types import ModuleType
from typing import Any, Protocol, runtime_checkable


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

    def _emit(self, level: str, message: str, **kwargs: Any) -> None:
        """ログ出力。context があれば付加する。"""
        context: Any | None = kwargs.get("context")
        suffix: str = ""
        if context:
            suffix = f" | context={pformat(context, compact=True)}"
        print(f"[{level}] [{self.name}] {message}{suffix}")

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

    get_logger_attr: Any | None = getattr(module, "get_logger", None)
    if not callable(get_logger_attr):
        return None

    get_logger: Callable[..., object] = get_logger_attr

    try:
        candidate: object = get_logger(name)
    except TypeError:
        candidate = get_logger()

    if isinstance(candidate, AlarmLogger):
        return candidate
    return None


def get_alarm_logger() -> AlarmLogger:
    """alarm 用 logger を返す。外部依存が無ければ簡易 logger を返す。"""

    logger: AlarmLogger | None = _load_external_logger("alarm")
    if logger is not None:
        return logger
    return FallbackLogger("alarm")
