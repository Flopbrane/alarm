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
from collections.abc import Callable
from datetime import datetime, timedelta

from alarm_internal_model import AlarmInternal
from ui_datetime_normalizer import normalize_base_date


class AlarmScheduler:
    """次回アラーム時刻を計算するクラス"""

    def __init__(self) -> None:
        # インスタンス固有の戦略表
        self.schedulers: dict[str, Callable[[AlarmInternal, datetime], datetime | None]]
        self.schedulers = {
            "single": self._next_single,
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

    # --------------------------------------------------------------
    # 🔹 single（単発アラーム）
    # --------------------------------------------------------------
    def _next_single(self, alarm: AlarmInternal, now: datetime) -> datetime:
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
    # 🔹 weekly（毎週 / n週おき）
    # --------------------------------------------------------------
    def _next_weekly(self, alarm: AlarmInternal, now: datetime) -> datetime:
        """weekly（毎週 / n週おき 共通）"""

        interval: int = alarm.interval_weeks or 1

        # ① 起点（日付）
        start: datetime = max(now, self._base(alarm))

        # ② 目標曜日（0=月〜6=日）
        target_weekday: int = alarm.datetime_.weekday()

        # ③ 次の該当曜日までの日数
        days_ahead: int = (target_weekday - start.weekday()) % 7

        # ④ 日付を進めて、時刻を合成
        candidate: datetime = self._with_time(
            start + timedelta(days=days_ahead),
            alarm,
        )

        # ⑤ 毎週（interval == 1）
        if interval == 1:
            if candidate <= now:
                candidate += timedelta(weeks=1)
            return candidate

        # ⑥ n週おき（interval >= 2）
        base: datetime | None = normalize_base_date(self._base(alarm), candidate)
        if not base:
            base = candidate

        while True:
            if candidate <= now:
                candidate += timedelta(weeks=1)
                continue
            weeks_diff: int = (candidate - base).days // 7
            if weeks_diff % interval != 0:
                candidate += timedelta(weeks=1)
                continue
            break

        return candidate

    # --------------------------------------------------------------
    # 🔹 monthly
    # --------------------------------------------------------------
    def _next_monthly(self, alarm: AlarmInternal, now: datetime) -> datetime:
        """monthly（毎月）の次回時刻を計算"""
        # monthly は「存在しない日付は月末に丸める」方針

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
