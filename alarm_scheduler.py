# -*- coding: utf-8 -*-
"""アラームの次回鳴動日時を計算するスケジューラ
alarm + now → datetime が返るか？
次回鳴動日時を計算するだけのモジュール

次は「いつ」鳴る予定か？=未来予測エンジン"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_scheduler.py
#########################

import calendar
from datetime import datetime, timedelta
from typing import Any, Dict

from alarm_internal_model import AlarmInternal
from alarm_repeat_rules import should_fire_alarm
from ui_datetime_normalizer import normalize_base_date


class AlarmScheduler:
    """次回アラーム時刻を計算するクラス"""

    def __init__(self) -> None:
        # インスタンス固有の戦略表
        self.schedulers: Dict[str, Any]
        self.schedulers = {
            "none": self._next_once,
            "daily": self._next_daily,
            "weekly": self._next_weekly,  # ← ここが入口
            "monthly": self._next_monthly,
            "custom": self._next_custom,
        }

    # ======================================================
    # _base()：基準日を1か所で決める
    # ======================================================
    def _base(self, alarm: AlarmInternal) -> datetime:
        """
        繰り返し計算の起点を返す。
        ※ AlarmManager により base_date_ は通常 None にならない前提
        """
        return alarm.repeat_base_datetime or alarm.datetime_

    # ======================================================
    # _with_time()：日付＋時刻の合成は必ずここ
    # ======================================================
    def _with_time(self, d: datetime, alarm: AlarmInternal) -> datetime:
        t: datetime = alarm.datetime_
        return d.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

    # ---------------------------------------
    # 次回アラーム時刻を取得
    # ---------------------------------------
    def get_next_time(self, alarm: AlarmInternal, now: datetime) -> datetime | None:
        """次回アラーム時刻を返す"""
        repeat: str
        repeat = alarm.repeat or "none"

        if repeat == "weekly":
            if alarm.interval_weeks and alarm.interval_weeks > 1:
                return self._next_weekly_x(alarm, now)
            return self._next_weekly(alarm, now)

        func: Any | None = self.schedulers.get(repeat)
        if func:
            return func(alarm, now)

        return None

    # --------------------------------------------------------------
    # 🔹 none（単発アラーム）
    # --------------------------------------------------------------
    def _next_once(self, alarm: AlarmInternal, now: datetime) -> datetime:
        # pylint: disable=unused-argument
        return alarm.datetime_

    # --------------------------------------------------------------
    # 🔹 daily（毎日）
    # --------------------------------------------------------------
    def _next_daily(self, alarm: AlarmInternal, now: datetime) -> datetime:
        """毎日設定の次回時刻（now 起点）
        設計思想（daily は now 起点）"""

        candidate: datetime = now.replace(
            hour=alarm.datetime_.hour,
            minute=alarm.datetime_.minute,
            second=0,
            microsecond=0,
        )

        if candidate <= now:
            candidate += timedelta(days=1)

        return candidate

    # --------------------------------------------------------------
    # 🔹 weekly（毎週）
    # --------------------------------------------------------------
    def _next_weekly(self, alarm: AlarmInternal, now: datetime) -> datetime:
        """毎週（interval_weeks == 1）の次回時刻を計算"""

        # ① 起点（日付）を決める
        start: datetime = max(now, self._base(alarm))

        # ② 目標曜日（0=月〜6=日）
        target_weekday: int = alarm.datetime_.weekday()

        # ③ 次の該当曜日までの日数
        days_ahead: int = (target_weekday - start.weekday()) % 7

        # ④ 日付を進めて、時刻を合成
        candidate: datetime = self._with_time(start + timedelta(days=days_ahead), alarm)

        # ⑤ 念のため「未来保証」
        if candidate <= now:
            candidate += timedelta(weeks=1)

        return candidate

    # --------------------------------------------------------------
    # 🔹 weekly（n週おき：2週〜）
    # --------------------------------------------------------------
    def _next_weekly_x(self, alarm: AlarmInternal, now: datetime) -> datetime:
        """weekly（n週おき：2週〜）"""
        interval: int = alarm.interval_weeks
        if interval < 2:
            return self._next_weekly(alarm, now)
        # weekly_x は「2以上」のときだけ有効

        start: datetime = max(now, self._base(alarm))
        target_weekday: int = alarm.datetime_.weekday()

        days_ahead: int = (target_weekday - start.weekday()) % 7
        candidate: datetime = self._with_time(start + timedelta(days=days_ahead), alarm)

        base: None | datetime = normalize_base_date(self._base(alarm), candidate)
        if not base:
            base = candidate

        while candidate <= now or (((candidate - base).days // 7) % interval != 0):
            candidate += timedelta(weeks=1)

        return candidate

    # --------------------------------------------------------------
    # 🔹 monthly
    # --------------------------------------------------------------
    def _next_monthly(self, alarm: AlarmInternal, now: datetime) -> datetime:
        start: datetime = max(now, self._base(alarm))
        target_day: int = alarm.datetime_.day

        year: int
        month: int
        year, month = start.year, start.month

        last_day: int = calendar.monthrange(year, month)[1]
        fire_day: int = min(target_day, last_day)

        candidate = datetime(
            year,
            month,
            fire_day,
            alarm.datetime_.hour,
            alarm.datetime_.minute,
        )

        if candidate <= now:
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

            last_day = calendar.monthrange(year, month)[1]
            fire_day = min(target_day, last_day)

            candidate = datetime(
                year,
                month,
                fire_day,
                alarm.datetime_.hour,
                alarm.datetime_.minute,
            )

        return candidate

    # --------------------------------------------------------------
    # 🔹 custom（曜日指定・第n週・週おき） → 上記の派生の組合せで別途実装可能
    # --------------------------------------------------------------
    def _next_custom(self, alarm: AlarmInternal, now: datetime) -> datetime | None:
        """custom（曜日指定・第n週・週おき）の次回時刻を計算"""

        # ① 起点（日付）を決める
        start: datetime = max(now, self._base(alarm))

        # ② 初期候補（起点日に時刻を合わせる）
        candidate: datetime = self._with_time(start, alarm)

        if candidate <= now:
            candidate += timedelta(days=1)

        # ③ 最大365日先まで探索
        for _ in range(366):

            # 曜日チェック（複数可）
            if alarm.weekday and candidate.weekday() not in alarm.weekday:
                candidate += timedelta(days=1)
                continue

            # 第 n 週チェック
            if alarm.week_of_month:
                week_num: int = (candidate.day - 1) // 7 + 1
                if week_num not in alarm.week_of_month:
                    candidate += timedelta(days=1)
                    continue

            # n週おきチェック
            if alarm.interval_weeks and alarm.interval_weeks > 1:
                base: None | datetime = normalize_base_date(
                    self._base(alarm), candidate
                )
                if base:
                    diff_weeks: int = (candidate - base).days // 7
                    if diff_weeks % alarm.interval_weeks != 0:
                        candidate += timedelta(days=1)
                        continue

            # 条件をすべて満たした
            return candidate

        return None

    # 🔥 その他の補助メソッドがあればここに追加

    def find_due_alarms(self, alarms: list[AlarmInternal]) -> list[AlarmInternal]:
        """鳴らすべきアラームデータを探す"""
        now: datetime = datetime.now()
        actual_now: datetime = now

        due: list[AlarmInternal] = []

        for alarm in alarms:
            if alarm.enabled and should_fire_alarm(alarm, now, actual_now):
                due.append(alarm)
        return due
