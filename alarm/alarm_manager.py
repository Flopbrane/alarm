"""AlarmManager の公開入口。

外部公開 API はこのファイルに集約し、実処理本体は
``alarm_manager_temp.py`` の ``AlarmManagerCore`` に委譲する。
"""
from alarm.alarm_manager_temp import (
    AlarmManagerCore,
    CycleOptions,
    CONFIG_CHANGED,
    NextAlarmInfo,
    TIMER_TICK,
    STARTUP_SYNC,
)

AlarmManager = AlarmManagerCore

__all__: list[str] = [
    "AlarmManager",
    "AlarmManagerCore",
    "CycleOptions",
    "CONFIG_CHANGED",
    "NextAlarmInfo",
    "TIMER_TICK",
    "STARTUP_SYNC",
]
