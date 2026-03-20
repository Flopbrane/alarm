# alarm/__init__.py
"""Alarmモジュールの初期化ファイル"""
from .logs.multi_info_logger import AppLogger, LogOutput

__all__: list[str] = ["AppLogger", "LogOutput"]
