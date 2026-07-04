# -*- coding: utf-8 -*-
# pylint: disable=C0301
"""CUIで駆動するアラームデータの入出力操作
✅ “CUI寄りのCLI”
メニューを出して「1/2/3/0」で選ばせる
これは CUI（文字メニューUI） の典型
ただしターミナル上で動いてるので CLI環境で動くCUIでもある
"""
#########################
# Author: F.Kurokawa
# Description:
# CUI入出力モジュール
#########################
# Future improvements:
from __future__ import annotations

# 標準モジュール
import sys
from datetime import datetime
from typing import Any, Literal, TextIO, cast, TYPE_CHECKING
import time

# 自作モジュール（順序を整理）
from alarm.alarm_ui_model import (
    AlarmDisplayRow,
    AlarmUI,
)
from alarm.constants import (
    DEFAULT_SOUND,
    REPEAT_INTERNAL,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_SNOOZE_MINUTES,
    DEFAULT_SNOOZE_LIMIT,
)
from alarm.alarm_manager_cycle_control_options import CUI_STARTUP
from alarm.cui_repeat_normalizer import normalize_repeat_input
from alarm.cui_datetime_normalizer import normalize_commas, validate_date, validate_time
from alarm.cui_weekday_normalizer import normalize_weekday_list
from alarm.cui_controller import CUIController
from utils.utils import select_sound_file
from utils.text_utils import to_hankaku

if TYPE_CHECKING:
    from alarm.alarm_manager import AlarmManager


# stdout の文字コードを UTF-8 に強制設定（Windows 対応）
stdout: TextIO = cast(TextIO, sys.stdout)
if hasattr(stdout, "reconfigure"):
    stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


# -----------定数--------------
CUI_UPCOMING_COUNT = 5
InputMode = Literal["raw", "half", "half_commas"]


# ======================================================
# 次のアラーム表示のための型ヒント定義
# ======================================================
# class NextAlarmInfo(TypedDict):
# """型ヒントの定義"""
# alarm: AlarmInternal
# next_datetime: datetime
# time_until: float


def format_repeat_for_display(repeat: str | None) -> str:
    """繰り返し設定を表示用文字列に変換する。"""
    repeat_map: dict[str, str] = {
        "none": "なし",
        "once": "一回のみ",
        "daily": "毎日",
        "weekly": "毎週",
        "monthly": "毎月",
        "yearly": "毎年",
    }

    if repeat is None:
        return "なし"

    return repeat_map.get(repeat, repeat)


def format_weekday_for_display(weekday: list[int] | None) -> str:
    """曜日番号を表示用文字列に変換する。0=月曜日。"""
    if not weekday:
        return ""

    weekday_map: dict[int, str] = {
        0: "月",
        1: "火",
        2: "水",
        3: "木",
        4: "金",
        5: "土",
        6: "日",
    }

    return ", ".join(weekday_map.get(w, str(w)) for w in weekday)


def print_upcoming_alarms(controller: CUIController) -> None:
    """次のアラームの表示(5件)"""
    controller.refresh_for_display()
    now: datetime = controller.manager.internal_clock()
    display_rows: list[AlarmDisplayRow] = controller.get_alarm_display_rows()
    if not display_rows:
        print("📭 有効なアラームがありません。")
        return

    print(f"\n⏰ 次に鳴動予定のアラーム（{len(display_rows)}件）:")
    print("-" * 60)

    for row in display_rows:
        next_datetime: datetime | None = row.next_alarm_datetime

        if next_datetime:
            time_until: float = (next_datetime - now).total_seconds()
            time_until = max(time_until, 0)

            hours = int(time_until // 3600)
            minutes = int((time_until % 3600) // 60)

            time_str: str = f"{hours}時間{minutes}分後" if hours > 0 else f"{minutes}分後"
        else:
            time_str = "不明"

        print(f"{row.row_no}: {row.name}")

        if next_datetime:
            print(f"   ⏰ {next_datetime.strftime('%Y/%m/%d %H:%M')} ({time_str})")
        else:
            print("   ⏰ 不明")

        repeat_text: str = format_repeat_for_display(row.repeat)
        print(f"   🔁 繰り返し: {repeat_text}")

        if row.weekday:
            print(f"   📅 曜日指定: {row.weekday}")

# ------------------------------------------
# 🔹 メインメニュー
# ------------------------------------------
def main(controller: CUIController) -> None:
    """メニュー表示"""
    controller.manager.start_cycle("startup", CUI_STARTUP)

    def run_alarm_monitor(manager: "AlarmManager") -> None:
        """アラーム監視開始"""
        print("🔁 アラーム監視開始（Ctrl+Cで停止）")
        try:
            while True:
                manager.start_cycle("loop")
                time.sleep(1) # 1秒ごとにチェック
        except KeyboardInterrupt:
            print("🛑 監視停止")

    def normalize_basic(text: str) -> str:
        """CUI入力向けの最低限の整形"""
        return text.replace("　", " ").strip()

    def input_with_mode(
        prompt: str,
        mode: InputMode = "raw",
        default: str = "",
    ) -> str:
        """入力値を正規化する"""
        s: str = input(f"{prompt} [qでキャンセル]: ").strip()
        if s.lower() == "q":
            raise KeyboardInterrupt
        if not s:
            return default

        if mode == "raw":
            return normalize_basic(s)
        elif mode == "half":
            return to_hankaku(s)
        elif mode == "half_commas":
            return normalize_commas(s)

        return s

    def input_repeat(default: str = "単発") -> str:
        """繰り返し設定を入力させ、内部表現を返す"""
        options: list[str] = list(REPEAT_INTERNAL.keys())
        print("繰り返しを選択してください:", ", ".join(options))

        default_key: str = default if default in REPEAT_INTERNAL else options[0]

        val: str = input_with_mode(
            f"繰り返し ({default_key})",
            mode="half",
            default=default_key,
        )
        return normalize_repeat_input(val, REPEAT_INTERNAL[default_key])

    def input_weekday_list() -> list[int]:
        raw: str = input_with_mode(
            "曜日（0=月〜6=日、または 月火水… をカンマ区切り、空欄可）",
            mode="half_commas",
            default="",
        )
        result: list[int] = normalize_weekday_list(raw)
        return result

    def input_week_of_month() -> list[int]:
        s: str = input_with_mode("第n週（1-6をカンマ区切り、6=最終週、空欄可）", mode="half")
        out: list[Any]
        if not s:
            return []
        out = []
        for part in s.split(","):
            part: str = part.strip()
            if part.isdigit():
                n = int(part)
                if 1 <= n <= 6:
                    out.append(n)
        return out

    def input_bool(prompt: str, default: bool = False) -> bool:
        default_str: Literal["y"] | Literal[""] = "y" if default else ""

        s: str = input_with_mode(
            f"{prompt} ({'Y/n' if default else 'y/N'})",
            mode="half",
            default=default_str,
        )

        if not s:
            return default

        return s.lower() in ("y", "yes", "1", "true")

    # -----メニューセレクト--------------------------
    while True:
        print("\n=== アラーム管理メニュー ===")
        print("1. アラーム追加")
        print("2. アラーム一覧")
        print("3. アラーム削除")
        print("4. 有効／無効切替")
        print("5. 時刻監視開始")
        print("0. 終了")

        choice: str = input("選択してください: ").strip()

        if choice == "1":
            try:
                name: str = input_with_mode("アラーム名(必須)", mode="raw")
                if not name:
                    print("アラーム名は必須です。")
                    continue

                date_str: str = input_with_mode("日付 (YYYY-MM-DD、省略可)", mode="half")
                normalized_date: str | None = validate_date(date_str) if date_str else date_str
                if date_str and normalized_date is None:
                    print("年月日の値が不適合です。")
                    continue
                date_str = normalized_date or date_str

                time_str: str = input_with_mode("時刻 (HH:MM)", mode="half")
                normalized_time: str | None = validate_time(time_str)
                if normalized_time is None:
                    print("時刻の値が不適合です。")
                    continue
                time_str = normalized_time

                repeat: str = input_repeat()

                weekday: list[int] = []
                week_of_month: list[int] = []
                interval_weeks: int = 0
                interval_days: int = 0

                if repeat == "weekly":
                    weekday = input_weekday_list()
                    interval_weeks = int(
                        input_with_mode("間隔(週)（デフォルト1）", mode="half", default="1")
                    )

                elif repeat == "custom":
                    weekday = input_weekday_list()
                    week_of_month = input_week_of_month()
                    interval_weeks = int(
                        input_with_mode("間隔(週)（デフォルト1）", mode="half", default="1")
                    )

                elif repeat == "daily":
                    interval_days = 1

                sound_input: str = input_with_mode(
                    "音ファイル名 (default.wav、省略可、'select'で選択)",
                    mode="half",
                    default=str(DEFAULT_SOUND),
                )

                if sound_input.lower() == "select":
                    sound: str = select_sound_file()
                else:
                    sound = sound_input or str(DEFAULT_SOUND)

                duration: int = int(input_with_mode("鳴動時間(秒)", mode="half", default=str(DEFAULT_DURATION_SECONDS)))
                snooze_minutes: int = int(input_with_mode("スヌーズ時間(分)", mode="half", default=str(DEFAULT_SNOOZE_MINUTES)))
                snooze_limit: int = int(
                    input_with_mode("スヌーズ上限(回、デフォルト3)", mode="half", default=str(DEFAULT_SNOOZE_LIMIT))
                )
                skip_holiday: bool = input_bool("祝日スキップしますか", default=False)

                # ✅ UIモデルだけ作る
                ui_alarm = AlarmUI(
                    id=None,  # Managerが付与
                    name=name,
                    date=date_str,
                    time=time_str,
                    repeat=repeat,
                    weekday=cast(list[int | str], weekday),
                    week_of_month=week_of_month,
                    interval_weeks=interval_weeks,
                    interval_days=interval_days,
                    custom_desc="",
                    enabled=True,
                    sound=str(sound),
                    skip_holiday=skip_holiday,
                    duration=duration,
                    snooze_minutes=snooze_minutes,
                    snooze_limit=snooze_limit,
                    end_at=None,
                )

                # 🔥 ここが重要
                controller.add_alarm_from_ui(ui_alarm)
                print("✅ アラームを追加しました。")

            except KeyboardInterrupt:
                print("入力をキャンセルしました。")

        elif choice == "2":
            print_upcoming_alarms(controller)

        elif choice == "3":
            row_no = int(input("削除する番号: "))
            if not controller.delete_alarm_by_row_no(row_no):
                print("無効な番号です")
                continue
            print("✅ アラームを削除しました。")

        elif choice == "4":
            row_no = int(input("切替する番号: "))
            if not controller.toggle_alarm_enabled_by_row_no(row_no):
                print("無効な番号です")
                continue

        elif choice == "5":
            run_alarm_monitor(controller.manager)

        elif choice == "0":
            print("終了します。")
            break

        else:
            print("無効な選択です。")


if __name__ == "__main__":
    from alarm.alarm_manager import AlarmManager

    main(CUIController(AlarmManager()))
