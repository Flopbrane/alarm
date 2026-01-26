# -*- coding: utf-8 -*-
"""アラームの次回鳴動日時を計算するスケジューラ
alarm + now → datetime が返るか？
次回鳴動日時を計算するだけのモジュール

次は「いつ」鳴る予定か？=未来予測エンジン

===Scheduler の正しい人格 👤===
Scheduler はこういう存在です。
「今がいつかは知らない。
でも、教えてくれたら計算は正確にやる。」
"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_scheduler.py
#########################
# NOTE:
# monthly は「毎月」のみ対応する。
# 隔月・nヶ月おきは本アプリのスコープ外。
# （それらはカレンダー/タスク管理の領域）
#########################
import calendar
from collections.abc import Callable
from datetime import datetime, timedelta

from alarm_internal_model import AlarmInternal
from cui_datetime_normalizer import normalize_base_date

# 型エイリアスをクラス外で定義
CallableType = Callable[[AlarmInternal, datetime], datetime | None]
# 上限定数
MAX_SINGLE_DAYS = 366  # 閏年考慮


class AlarmScheduler:
    """次回アラーム時刻を計算するクラス"""

    def __init__(self) -> None:
        # インスタンス固有の戦略表
        self._handlers: dict[str, CallableType] = {
            "single": self._next_single,
            "daily": self._next_daily,
            "weekly": self._next_weekly,
            "monthly": self._next_monthly,
            "interval_days": self._next_interval_days,  # daily と同じロジック
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
    def get_next_time(
        self,
        alarm: AlarmInternal,
        now: datetime,
    ) -> datetime | None:
        """次回アラーム時刻を取得"""
        if not alarm.enabled:
            return None

        repeat: str = alarm.repeat or "single"

        handler: CallableType | None = self._get_handler(repeat)

        if handler is None:
            return None
        return handler(alarm, now)

    def _get_handler(self, repeat: str) -> CallableType | None:
        return self._handlers.get(repeat)

    # --------------------------------------------------------------
    # 🔹 single（単発アラーム）
    # --------------------------------------------------------------
    def _next_single(self, alarm: AlarmInternal, now: datetime) -> datetime | None:
        dt: datetime = alarm.datetime_

        # 過去は無効
        if dt <= now:
            return None  # 過去は「もう無い」

        # 未来上限（1年）
        if dt > now + timedelta(days=MAX_SINGLE_DAYS):
            return None  # 上限超えは扱わない

        return dt

    # --------------------------------------------------------------
    # 🔹 daily（毎日）
    # --------------------------------------------------------------
    def _next_daily(self, alarm: AlarmInternal, now: datetime) -> datetime | None:
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
    # 🔹 interval_days(◯日おき)
    # --------------------------------------------------------------
    def _next_interval_days(
        self,
        alarm: AlarmInternal,
        now: datetime,
    ) -> datetime | None:
        """◯日おき設定の次回時刻（now 起点）"""
        interval: int = alarm.interval_days or 0
        if interval <= 0:
            return None

        base: datetime = alarm.datetime_

        candidate: datetime = base
        while candidate <= now:
            candidate += timedelta(days=interval)

        return candidate

    # --------------------------------------------------------------
    # 🔹 補助関数（曜日リストから次の候補日を作る）
    # --------------------------------------------------------------
    def _next_weekday_candidate(
        self,
        start: datetime,
        weekdays: list[int],
    ) -> datetime:
        """start から見て、weekdays のいずれかに当たる最短日を返す（時刻は start のまま）"""
        # 0=月 ... 6=日 を前提
        wset: list[int] = sorted(set(weekdays))
        best_delta: int | None = None

        for wd in wset:
            delta: int = (wd - start.weekday()) % 7
            if best_delta is None or delta < best_delta:
                best_delta = delta

        assert best_delta is not None
        return start + timedelta(days=best_delta)

    # --------------------------------------------------------------
    # 🔹 weekly（毎週 / n週おき）
    # --------------------------------------------------------------
    def _next_weekly(self, alarm: AlarmInternal, now: datetime) -> datetime:
        """weekly（毎週 / n週おき 共通）"""

        interval: int = alarm.interval_weeks or 1

        # ① 起点（日付）
        start: datetime = max(now, self._base(alarm))

        # ★曜日リスト優先（なければ datetime_ の曜日）
        weekdays: list[int] = (
            alarm.weekday if alarm.weekday else [alarm.datetime_.weekday()]
        )
        weekdays = sorted(set(weekdays))

        # 次に来る曜日へ
        day_candidate: datetime = self._next_weekday_candidate(start, weekdays)

        # 時刻合成(次の曜日の日付 + AlarmIntenal.datetime_.time())
        candidate: datetime = self._with_time(day_candidate, alarm)

        # 今を過ぎていたら「次の曜日候補」へ進める
        if candidate <= now:
            # 次の日から探し直す（同週内の別曜日にも行ける）
            start2: datetime = (candidate + timedelta(days=1)).replace(
                hour=start.hour, minute=start.minute, second=start.second, microsecond=0
            )
            day_candidate = self._next_weekday_candidate(start2, weekdays)
            candidate = self._with_time(day_candidate, alarm)

        # ⑤ 毎週（interval == 1）
        if interval == 1:
            if candidate <= now:
                candidate += timedelta(weeks=1)
            return candidate

        # n週おき: base週との差分が interval の倍数になるまで進める
        base: datetime | None = normalize_base_date(self._base(alarm), candidate)
        if not base:
            base = candidate

        # ★ここがコツ：週を進めるときも「次の曜日候補」で探す
        while True:
            weeks_diff: int = (candidate.date() - base.date()).days // 7
            if weeks_diff % interval == 0 and candidate > now:
                return candidate

            # 次候補へ（翌日から探す→同週内/次週内を自動で拾う）
            start2: datetime = (candidate + timedelta(days=1)).replace(
                hour=start.hour, minute=start.minute, second=start.second, microsecond=0
            )
            day_candidate = self._next_weekday_candidate(start2, weekdays)
            candidate = self._with_time(day_candidate, alarm)

    # --------------------------------------------------------------
    # 🔹 monthly
    # --------------------------------------------------------------
    def _next_monthly(self, alarm: AlarmInternal, now: datetime) -> datetime:
        """monthly（毎月）の次回時刻を計算
        monthly はこういう存在です：
        ・毎月 1 回
        ・「日付＋時刻」を基準に
        ・次に来る 1回分 の日時を返すだけ"""
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
        """custom（曜日・第n週・n週おきの組合せ）"""

        start: datetime = max(now, self._base(alarm))
        candidate: datetime = self._with_time(start, alarm)

        if candidate <= now:
            candidate += timedelta(days=1)

        for _ in range(180):  # 約6か月

            # --- 月内条件（custom固有） ---
            if alarm.week_of_month:
                week_num: int = (candidate.day - 1) // 7 + 1
                if week_num not in alarm.week_of_month:
                    candidate += timedelta(days=1)
                    continue

            # --- 曜日条件 ---
            if alarm.weekday and candidate.weekday() not in alarm.weekday:
                candidate += timedelta(days=1)
                continue

            # --- n週おき条件（weeklyと同一思想） ---
            if alarm.interval_weeks and alarm.interval_weeks > 1:
                base: datetime | None = normalize_base_date(
                    self._base(alarm), candidate
                )
                if base:
                    diff_weeks: int = (candidate - base).days // 7
                    if diff_weeks % alarm.interval_weeks != 0:
                        candidate += timedelta(days=1)
                        continue

            return candidate

        return None

    # 🔥 その他の補助メソッドがあればここに追加
