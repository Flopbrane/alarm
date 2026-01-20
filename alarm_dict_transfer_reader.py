# -*- coding: utf-8 -*-
"""ファイル入出力から、JSONモデルへの変換ラッパー
このファイルの責務：
- dict → AlarmJson のみ
- dict → AlarmStateJson のみ
Internal 変換は禁止
"""
#########################
# Author: F.Kurokawa
# Description:
# UIモデルからJSONモデルへの変換ラッパー(チェック済み)
#########################
from typing import Any, Dict

from alarm_json_model import AlarmJson, AlarmStateJson
from constants import DEFAULT_SOUND


class AlarmJsonDictAdapter:
    """Dict ↔ JSON dataclass 変換・受渡し"""

    # ========== 🔹★Dict → dataclass 変換★ ==========
    # UIファイル読み込み、書き出し時にDictに変換する
    # -------------------------------------------------------
    # ★dict → AlarmJson
    # -------------------------------------------------------
    @staticmethod
    def dict_to_alarm_json(d: Dict[str, Any]) -> AlarmJson:
        """dict → AlarmJson"""
        return AlarmJson(
            id=int(d.get("id", 0)),
            name=d.get("name", ""),
            date=d.get("date", ""),
            time=d.get("time", ""),
            repeat=d.get("repeat", "none"),
            weekday=list(d.get("weekday", [])),
            week_of_month=list(d.get("week_of_month", [])),
            interval_weeks=int(d.get("interval_weeks", 1)),
            base_date=d.get("base_date"),
            custom_desc=d.get("custom_desc", ""),
            enabled=bool(d.get("enabled", True)),
            sound=d.get("sound", DEFAULT_SOUND),
            skip_holiday=bool(d.get("skip_holiday", False)),
            duration=int(d.get("duration", 10)),
            snooze_minutes=int(d.get("snooze_minutes", 10)),
            snooze_limit=int(d.get("snooze_limit", 3)),
        )

    # ---------------------------------------------------
    # ★dict → AlarmStateJson
    # ---------------------------------------------------
    @staticmethod
    def dict_to_alarm_state_json(d: Dict[str, Any]) -> AlarmStateJson:
        """dict → AlarmStateJson"""
        return AlarmStateJson(
            id=int(d.get("id", 0)),
            _snoozed_until=d.get("_snoozed_until"),
            _snooze_count=int(d.get("_snooze_count", 0)),
            _triggered=bool(d.get("_triggered", False)),
            _triggered_at=d.get("_triggered_at"),
            _last_fired_at=d.get("_last_fired_at"),
            _next_fire_datetime=d.get("_next_fire_datetime"),
        )
