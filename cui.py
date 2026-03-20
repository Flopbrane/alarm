# -*- coding: utf-8 -*-
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

# 自作モジュール（順序を整理）
from alarm_internal_model import AlarmInternal
from alarm_ui_model import (
    AlarmUI,
    AlarmUIPatch,
    AlarmListItem,
)  # ← UI層のAlarmState定義
from constants import DEFAULT_SOUND, REPEAT_INTERNAL
from data_ui_to_mgr_adapter import CUIController
from cui_datetime_normalizer import normalize_commas, validate_date, validate_time
from cui_weekday_normalizer import normalize_weekday_list
from utils.utils import select_sound_file
from utils.text_utils import to_hankaku
from alarm_payloads import AddPayload, UpdatePayload, DeletePayload


if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager


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

def print_upcoming_alarms(manager: "AlarmManager") -> None:
    """次のアラームの表示(5件)"""
    manager.start_cycle("loop")
    now: datetime = manager.internal_clock()
    next_infos: list[AlarmListItem] = manager.get_alarm_list()
    if not next_infos:
        print("📭 有効なアラームがありません。")
        return

    print(f"\n⏰ 次に鳴動予定のアラーム（{len(next_infos)}件）:")
    print("-" * 60)

    for i, info in enumerate(next_infos, 1):
        display_id: int = i  # UI専用番号
        alarm_ui: AlarmUI = info.alarm_ui
        next_datetime: datetime | None = info.next_datetime

        if next_datetime:
            time_until: float = (next_datetime - now).total_seconds()
            time_until = max(time_until, 0)

            hours = int(time_until // 3600)
            minutes = int((time_until % 3600) // 60)

            time_str: str = f"{hours}時間{minutes}分後" if hours > 0 else f"{minutes}分後"
        else:
            time_str = "不明"

        print(f"{display_id}: {alarm_ui.name}")

        if next_datetime:
            print(f"   ⏰ {next_datetime.strftime('%Y/%m/%d %H:%M')} ({time_str})")
        else:
            print("   ⏰ 不明")

        print(f"   🔁 繰り返し: {alarm_ui.repeat}")

        if alarm_ui.weekday:
            print(f"   📅 曜日指定: {', '.join(str(w) for w in alarm_ui.weekday)}")


# ------------------------------------------
# 🔹 メインメニュー
# ------------------------------------------
def main(alarm_manager: "AlarmManager") -> None:
    """メニュー表示"""
    controller = CUIController(alarm_manager)

    def run_alarm_monitor(controller: CUIController) -> None:
        """アラーム監視ループを開始する（CUI補助）"""
        print("🔁 アラーム監視開始（Ctrl+Cで停止）")
        try:
            controller.run()
        except KeyboardInterrupt:
            controller.stop()
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

        return REPEAT_INTERNAL.get(val, REPEAT_INTERNAL[default_key])

    def input_weekday_list() -> list[int]:
        raw: str = input_with_mode(
            "曜日（0=月〜6=日、または 月火水… をカンマ区切り、空欄可）",
            mode="half_commas",
            default="",
        )
        result: list[int] = normalize_weekday_list(raw)
        return result

    def input_week_of_month() -> list[int]:
        s: str = input_with_mode("第n週（1-5をカンマ区切り、空欄可）", mode="half")
        out: list[Any]
        if not s:
            return []
        out = []
        for part in s.split(","):
            part: str = part.strip()
            if part.isdigit():
                n = int(part)
                if 1 <= n <= 5:
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
                if date_str and not validate_date(date_str):
                    print("年月日の値が不適合です。")
                    continue

                time_str: str = input_with_mode("時刻 (HH:MM)", mode="half")
                if not validate_time(time_str):
                    print("時刻の値が不適合です。")
                    continue

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

                duration: int = int(input_with_mode("鳴動時間(秒)", mode="half", default="10"))
                snooze_limit: int = int(
                    input_with_mode("スヌーズ上限(回、デフォルト3)", mode="half", default="3")
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
                    snooze_minutes=alarm_manager.snooze_default,
                    snooze_limit=snooze_limit,
                    end_at=None,
                )

                # 🔥 ここが重要
                payload = AddPayload(ui_alarm=ui_alarm)
                alarm_manager.apply_alarm_mutation("add", payload)
                print("✅ アラームを追加しました。")

            except KeyboardInterrupt:
                print("入力をキャンセルしました。")


        elif choice == "2":
            print_upcoming_alarms(alarm_manager)

        elif choice == "3":
            alarm_list = alarm_manager.get_alarm_list()
            index = int(input("削除する番号: ")) - 1
            if not 0 <= index < len(alarm_list):
                print("無効な番号です")
                continue
            alarm_id = alarm_list[index].alarm_id
            payload = DeletePayload(alarm_id_list=[alarm_id])
            alarm_manager.apply_alarm_mutation("delete", payload)
            print("✅ アラームを削除しました。")

        elif choice == "4":
            alarm_list: list[AlarmListItem] = alarm_manager.get_alarm_list()
            index: int = int(input("切替する番号: ")) - 1
            if not 0 <= index < len(alarm_list):
                print("無効な番号です")
                continue
            alarm_id: str = alarm_list[index].alarm_id
            alarm: AlarmInternal | None = alarm_manager.get_alarm_by_id(alarm_id)

            if alarm is None:
                print("アラームが見つかりません")
                continue
            patch = AlarmUIPatch(enabled=not alarm.enabled)
            payload = UpdatePayload(
                alarm_id=alarm_id,
                patch=patch
            )
            alarm_manager.apply_alarm_mutation("update", payload)

        elif choice == "5":
            run_alarm_monitor(controller)

        elif choice == "0":
            print("終了します。")
            break

        else:
            print("無効な選択です。")
