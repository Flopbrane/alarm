# -*- coding: utf-8 -*-
# pylint: disable=W0212
"""繰り返しルール判定モジュール
alarm + now + actual_now → True/False
(鳴らすか？鳴らさないか？の判定が役割)

今この瞬間に「鳴らしていいか」？=発火判定エンジン"""
#########################
# Author: F.Kurokawa
# Description:
# 繰り返しルール判定モジュール
#########################

import calendar
from datetime import datetime, time
from typing import Callable, List

from alarm_internal_model import AlarmInternal, AlarmStateInternal
from date_rule_valid_util import is_valid_interval_week, is_valid_week_of_month
from ui_datetime_normalizer import normalize_base_date


# --------------------------------------------------------------
# 🔹 共通ユーティリティ
# --------------------------------------------------------------
def _check_last_fire(state: AlarmStateInternal | AlarmInternal, actual_now: datetime) -> bool:
    """直前発火チェック（5秒以内は無視）"""
    # support being passed either an AlarmStateInternal or a full AlarmInternal
    last_fire: datetime | None = getattr(state, "last_fired_at", None)
    if last_fire and (actual_now - last_fire).total_seconds() < 5:
        return False
    return True


def match_time(a: datetime | time, b: datetime | time) -> bool:
    """日付時刻/時刻のようなオブジェクトの時間と分を比較します。"""
    try:
        a_hm: tuple[int, int] = (a.hour, a.minute)
    except AttributeError:
        return False

    try:
        b_hm: tuple[int, int] = (b.hour, b.minute)
    except AttributeError:
        return False

    return a_hm == b_hm


# --------------------------------------------------------------
# 🔹 daily
# --------------------------------------------------------------
def check_daily_rule(alarm: AlarmInternal, now: datetime, actual_now: datetime) -> bool:
    """毎日設定の時の時刻計算"""
    alarm_time: datetime | time = alarm.datetime_
    if not isinstance(alarm_time, time):
        return False

    if not match_time(now.time(), alarm_time):
        return False

    return _check_last_fire(alarm, actual_now)


# --------------------------------------------------------------
# 🔹 weekly（毎週◯曜日）と　n週おき　に対応
# --------------------------------------------------------------
def check_weekly_rule(
    alarm: AlarmInternal, now: datetime, actual_now: datetime
) -> bool:
    """weeklyとweekly_xの両対応"""
    alarm_time: datetime = alarm.datetime_

    # 曜日一致
    if now.weekday() != alarm_time.weekday():
        return False

    # 時刻一致
    if not match_time(now.time(), alarm_time):
        return False

    interval: int = alarm.interval_weeks or 1

    # 毎週（interval == 1）
    if interval == 1:
        return _check_last_fire(alarm, actual_now)

    # n週おき（2週以上）

    base_date: datetime | None = normalize_base_date(
        alarm.base_date_ or alarm_time,
        alarm_time,
    )
    if base_date is None:
        return False

    if not is_valid_interval_week(
        now.isocalendar().week,
        base_date.isocalendar().week,
        interval,
    ):
        return False

    return _check_last_fire(alarm, actual_now)


# --------------------------------------------------------------
# 🔹 monthly（毎月◯日＋月末補正）
# --------------------------------------------------------------
def check_monthly_rule(
    alarm: AlarmInternal, now: datetime, actual_now: datetime
) -> bool:
    """毎月設定の時の時刻計算"""
    alarm_time: datetime = alarm.datetime_
    target_day: int = alarm_time.day

    year: int
    month: int
    year, month = now.year, now.month
    last_day: int = calendar.monthrange(year, month)[1]

    if target_day <= last_day:
        fire_day: int = target_day
    else:
        # 存在しない日 → 翌月1日
        next_month: int = month + 1
        next_year: int = year
        if next_month == 13:
            next_month = 1
            next_year += 1

        fire = datetime(next_year, next_month, 1, alarm_time.hour, alarm_time.minute)
        if now.date() != fire.date():
            return False
        if not match_time(now.time(), alarm_time):
            return False
        return _check_last_fire(alarm, actual_now)

    # 存在する日の場合
    fire = datetime(year, month, fire_day, alarm_time.hour, alarm_time.minute)
    if now.date() != fire.date():
        return False
    if not match_time(now.time(), alarm_time):
        return False

    return _check_last_fire(alarm, actual_now)


# --------------------------------------------------------------
# 🔹 custom（曜日指定・第n週・週おき）
# --------------------------------------------------------------
def check_custom_rule(
    alarm: AlarmInternal, now: datetime, actual_now: datetime
) -> bool:
    """custom（曜日指定・第n週・週おき）の時の時刻計算"""
    alarm_time: datetime = alarm.datetime_

    # ① 曜日
    weekdays: List[int] = alarm.weekday or []
    if weekdays and now.weekday() not in weekdays:
        return False

    # ② 第n週
    if not is_valid_week_of_month(now, alarm.week_of_month or []):
        return False

    # ③ 週おき
    interval: int = alarm.interval_weeks or 1
    base_date: datetime | None
    base_date = normalize_base_date(
        alarm.repeat_base_datetime or alarm_time, alarm_time
    )
    if not base_date:
        return False

    if not is_valid_interval_week(
        now.isocalendar().week, base_date.isocalendar().week, interval
    ):
        return False

    # ④ 時刻一致
    if not match_time(now.time(), alarm_time):
        return False

    return _check_last_fire(alarm, actual_now)


# --------------------------------------------------------------
# 🔹 single（単発アラーム）
# --------------------------------------------------------------
def check_single_rule(alarm: AlarmInternal, now: datetime, actual_now: datetime) -> bool:
    """単発アラームの時の時刻計算"""
    alarm_time: datetime = alarm.datetime_
    if now.strftime("%Y-%m-%d %H:%M") != alarm_time.strftime("%Y-%m-%d %H:%M"):
        return False
    return _check_last_fire(alarm, actual_now)


# --------------------------------------------------------------
# 🔹 ルールマッピング
# --------------------------------------------------------------
REPEAT_RULE_CHECKERS: dict[str, Callable[..., bool]] = {
    "daily": check_daily_rule,
    "weekly": check_weekly_rule,  # ← 入口はこれだけ
    "monthly": check_monthly_rule,
    "custom": check_custom_rule,
    "single": check_single_rule,
}


# --------------------------------------------------------------
# 🔹 repeat 設定に応じて、本当に鳴らして良いのかの最終判断
# --------------------------------------------------------------
def should_fire_alarm(
    alarm: AlarmInternal,
    now: datetime,
    actual_now: datetime,
) -> bool:
    """repeat 設定に応じて、発火すべきか判定する唯一の入口"""

    rule: str = alarm.repeat

    checker: Callable[..., bool] | None = REPEAT_RULE_CHECKERS.get(rule)
    if not checker:
        return False

    return checker(alarm, now, actual_now)


# --------------------------------------------------------------
# 🔹 single（単発アラーム・デバッグ用）
# --------------------------------------------------------------
def check_single_rule_debug(
    alarm: AlarmInternal, now: datetime, actual_now: datetime
) -> bool:
    """単発アラームの時の時刻計算"""
    alarm_time: datetime = alarm.datetime_
    if now.strftime("%Y-%m-%d %H:%M") != alarm_time.strftime("%Y-%m-%d %H:%M"):
        return False
    return _check_last_fire(alarm, actual_now)
