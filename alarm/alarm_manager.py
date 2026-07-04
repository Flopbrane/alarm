"""AlarmManager の公開入口。

外部公開 API はこのファイルに集約し、実処理本体は
``alarm_manager_temp.py`` の ``AlarmManagerCore`` に委譲する。
"""
from __future__ import annotations

from typing import TypeAlias

from alarm.alarm_manager_temp import (
    AlarmManagerCore,
    CycleOptions,
    CONFIG_CHANGED,
    NextAlarmInfo,
    TIMER_TICK,
    STARTUP_SYNC,
)


# 互換用エイリアス:
# 旧コードが AlarmManager() で起動できるように、
# 実体は AlarmManagerCore クラスへ委譲する。
AlarmManager: TypeAlias = AlarmManagerCore  # pylint: disable=invalid-name

__all__: list[str] = [
    "AlarmManager",
    "AlarmManagerCore",
    "CycleOptions",
    "CONFIG_CHANGED",
    "NextAlarmInfo",
    "TIMER_TICK",
    "STARTUP_SYNC",
]
