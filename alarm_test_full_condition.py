# -*- coding: utf-8 -*-
"""
alarm_test_full_condition.py
全パターンのアラーム計算テストを行うスクリプト
Author: F.Kurokawa（テスト支援 by 先生）
"""
import copy
from datetime import datetime
from typing import Any

from alarm_internal_model import AlarmInternal
from alarm_scheduler import AlarmScheduler


class AlarmTestBase:
    """テスト用の疑似AlarmInternal"""

    def __init__(self) -> None:
        self.base_alarm = AlarmInternal(
            id=0,
            name="test",
            datetime_=datetime(2025, 1, 1, 10, 5),
            repeat="none",
            weekday=[3],
            week_of_month=[1, 3],
            interval_weeks=1,
            base_date_=datetime(2024, 12, 15, 16, 30),
        )

    def make_alarm(self, **kwargs) -> AlarmInternal:
        """テストごとの差分を指定して AlarmInternal を生成する"""
        alarm: AlarmInternal = copy.deepcopy(self.base_alarm)
        for k, v in kwargs.items():
            setattr(alarm, k, v)
        return alarm


def print_header(title: str) -> None:
    """導入表示"""
    print("\n" + "=" * 60)
    print("🧪 TEST:", title)
    print("=" * 60)


def show(result, expect=None) -> None:
    """次のアラームを表示"""
    print(f"➡ next = {result}")
    if expect:
        print(f"   (expected ≈ {expect})")


def test_once() -> None:
    """単発テスト"""
    print_header("単発 (none)")

    base = AlarmTestBase()
    alarm: AlarmInternal = base.make_alarm(
        id=1,
        repeat="none",
    )
    sch = AlarmScheduler()
    now: datetime = alarm.datetime_
    # 単発は繰り返しテストは行いません。
    # なぜなら、2回目以降に"None"が返ってくるからです。
    next_time = sch.get_next_time(alarm, now)
    show(next_time)


def test_daily() -> None:
    """毎日設定テスト"""
    print_header("毎日 (daily)")
    now = datetime(2025, 1, 1, 9, 0)
    base = AlarmTestBase()
    alarm: AlarmInternal = base.make_alarm(
        id=2,
        name="daily",
        datetime_=datetime(2025, 1, 1, 10, 5),
        repeat="daily",
        base_date_=datetime(2024, 12, 15, 16, 30),
    )
    sch = AlarmScheduler()
    next_time: datetime | None
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time


def test_weekly() -> None:
    """毎週設定テスト"""
    print_header("毎週 (weekly)")
    # 2025/1/1 は水曜日（weekday = 2）
    next_time: datetime | None
    now = datetime(2025, 1, 1, 10, 30)
    base = AlarmTestBase()
    alarm: AlarmInternal = base.make_alarm(
        id=3,
        name="weekly",
        datetime_=datetime(2025, 1, 1, 10, 5),  # 水曜10:05
        repeat="weekly",
        interval_weeks=1,
        repeat_base_datetime=datetime(2024, 12, 18, 10, 5),
    )

    sch = AlarmScheduler()
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time


def test_weekly_x() -> None:
    """week_xテスト"""
    print_header("隔週 / 3週おき (weekly_n)")
    now = datetime(2025, 1, 1, 10, 30)
    next_time: Any | None

    base = AlarmTestBase()
    alarm: AlarmInternal = base.make_alarm(
        id=4,
        name="weekly_x",
        datetime_=datetime(2025, 1, 1, 10, 5),  # 水曜10:05
        repeat="weekly",
        interval_weeks=3,
        base_date_=datetime(2025, 1, 1, 10, 5),
    )

    if alarm.repeat == "weekly" and alarm.interval_weeks > 1:
        sch = AlarmScheduler()
        for _ in range(3):
            next_time = sch.get_next_time(alarm, now)
            show(next_time)
            if next_time:
                now: datetime = next_time


def test_monthly() -> None:
    """毎月設定テスト"""
    print_header("毎月 (monthly)")
    now = datetime(2025, 1, 15, 12, 0)
    next_time: Any | None
    base = AlarmTestBase()
    alarm: AlarmInternal = base.make_alarm(
        id=5,
        name="monthly",
        datetime_=datetime(2025, 1, 31, 10, 5),  # 31日
        repeat="monthly",
        base_time=datetime(2025, 1, 31, 10, 5),
    )

    sch = AlarmScheduler()
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time
    # next_time = sch.get_next_time(alarm, now)
    # show(next_time, "2/28 10:05 になるはず（2月は28日まで）")


# ============= custom_test ===================
def test_custom_weekday_only() -> None:
    """曜日のみ指定"""
    print_header("custom（曜日のみ指定）")
    next_time: Any | None
    now = datetime(2025, 1, 1, 10, 30)
    test_base = AlarmTestBase()
    alarm: AlarmInternal = test_base.make_alarm(
        id=7,
        name="custom_weekday",
        datetime_=datetime(2025, 1, 1, 10, 5),
        repeat="custom",
        weekday=[2],
        week_of_month=[],
        interval_weeks=1,
        base_date_=datetime(2025, 1, 1, 10, 5),
    )

    sch = AlarmScheduler()
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time


def test_custom_week_of_month_only() -> None:
    """第n週のみ指定"""
    print_header("custom（第n週のみ指定）")
    next_time: Any | None
    now = datetime(2025, 1, 1, 10, 30)
    test_base = AlarmTestBase()
    alarm: AlarmInternal = test_base.make_alarm(
        id=8,
        name="custom_week_of_month",
        datetime_=datetime(2025, 1, 1, 10, 5),
        repeat="custom",
        weekday=[2],  # 曜日指定（0=月〜6=日）
        week_of_month=[1, 3],  # 第n週指定（1〜5）
        interval_weeks=1,  # 何週おきか（1=毎週、2=隔週、3=3週おき…）
        base_date_=datetime(2025, 1, 1, 10, 5),
    )

    sch = AlarmScheduler()
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time


def test_custom_interval_weeks_only() -> None:
    """n週おきのみ指定"""
    print_header("custom（n週おきのみ指定）")
    next_time: Any | None
    now = datetime(2025, 1, 1, 10, 30)
    test_base = AlarmTestBase()
    alarm: AlarmInternal = test_base.make_alarm(
        id=9,
        name="custom_interval",
        datetime_=datetime(2025, 1, 1, 10, 5),
        repeat="custom",
        weekday=[2, 4],  # 曜日指定（0=月〜6=日）
        week_of_month=[],  # 第n週指定（1〜5）
        interval_weeks=2,  # 何週おきか（1=毎週、2=隔週、3=3週おき…）
        base_date_=datetime(2025, 1, 1, 10, 5),
    )

    sch = AlarmScheduler()
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time


def test_custom_full_combo() -> None:
    """曜日 + 第n週 + n週おき（最終確認）"""
    print_header("custom（曜日 + 第n週 + n週おき全組合わせ）")
    next_time: Any | None
    now = datetime(2025, 1, 1, 10, 30)
    test_base = AlarmTestBase()
    alarm: AlarmInternal = test_base.make_alarm(
        id=10,
        name="custom_full",
        datetime_=datetime(2025, 1, 1, 10, 5),
        repeat="custom",
        weekday=[2, 4],
        week_of_month=[1, 3],
        interval_weeks=2,
        base_date_=datetime(2025, 1, 1, 10, 5),
    )

    sch = AlarmScheduler()
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time


def test_custom() -> None:
    """custom設定テスト"""
    print_header("custom（曜日 + 第n週 + 週おき）")
    next_time: Any | None
    now = datetime(2025, 1, 1, 10, 30)  # 水曜
    base = AlarmTestBase()
    alarm: AlarmInternal = base.make_alarm(
        id=6,
        name="custom",
        datetime_=datetime(2025, 1, 1, 10, 5),
        repeat="custom",
        weekday=[2],  # 水曜
        week_of_month=[1, 3],  # 第1週
        interval_weeks=2,
        base_date_=datetime(2025, 1, 1, 10, 5),
    )

    sch = AlarmScheduler()
    for _ in range(3):
        next_time = sch.get_next_time(alarm, now)
        show(next_time)
        if next_time:
            now: datetime = next_time
    # next_time = sch.get_next_time(alarm, now)
    # show(next_time, "2025/1/1 10:05 → 当日扱い or 翌週判定")


if __name__ == "__main__":
    print("🔎 Alarm Scheduler 全テスト開始…")

    test_once()
    test_daily()
    test_weekly()
    test_weekly_x()
    test_monthly()
    test_custom_weekday_only()
    test_custom_week_of_month_only()
    test_custom_interval_weeks_only()
    test_custom_full_combo()
    test_custom()

    print("\n🎉 全テスト実行完了！")
