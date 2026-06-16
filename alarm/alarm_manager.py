"""AlarmManager の公開入口。

既存コードの実体は ``alarm_manager_temp.py`` にあるため、
外部モジュールはこのファイル経由で参照する。
"""
from alarm_manager_temp import (
    AlarmManager,
    CycleOptions,
    CONFIG_CHANGED,
    RUNNING,
    STARTUP,
)

__all__: list[str] = [
    "AlarmManager",
    "CycleOptions",
    "CONFIG_CHANGED",
    "RUNNING",
    "STARTUP",
]
