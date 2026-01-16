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
# 標準モジュール
import sys
from datetime import datetime
from typing import Any, Literal, TextIO, cast

from alarm_internal_model import AlarmInternal, AlarmStateInternal

# 自作モジュール（順序を整理）
from alarm_manager import AlarmManager, NextAlarmInfo
from alarm_ui_model import AlarmUI
from constants import DEFAULT_SOUND, REPEAT_INTERNAL
from ui_datetime_normalizer import normalize_commas
from ui_weekday_normalizer import normalize_weekday_list
from utils import select_sound_file, validate_date, validate_time
from utils.text_utils import to_hankaku

# stdout の文字コードを UTF-8 に強制設定（Windows 対応）
stdout: TextIO = cast(TextIO, sys.stdout)
if hasattr(stdout, "reconfigure"):
    stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


# -----------定数--------------
CUI_UPCOMING_COUNT = 5
InputMode = Literal["raw", "half", "half_commas"]


# ======================================================
# 次のアラーム表示(cui.py デバッグ用)
# ======================================================
def print_upcoming_alarms(manager: AlarmManager, count: int = 5) -> None:
    """次のアラームの表示(5件)"""
    next_infos: list[NextAlarmInfo] = manager.get_next_alarms(count)
    if not next_infos:
        print("📭 有効なアラームがありません。")
        return

    print(f"\n⏰ 次に鳴動予定のアラーム（{len(next_infos)}件）:")
    print("-" * 60)

    for i, info in enumerate(next_infos, 1):
        alarm: AlarmInternal = info["alarm"]
        next_dt: datetime = info["next_datetime"]
        time_until: float = info["time_until"]

        hours = int(time_until // 3600)
        minutes = int((time_until % 3600) // 60)
        time_str: str = f"{hours}時間{minutes}分後" if hours > 0 else f"{minutes}分後"

        print(f"{i}. [{alarm.id}] {alarm.name}")
        print(f"   ⏰ {next_dt.strftime('%Y/%m/%d %H:%M')} ({time_str})")
        print(f"   🔁 繰り返し: {alarm.repeat}")

        if alarm.weekday:
            print(f"   📅 曜日指定: {', '.join(str(w) for w in alarm.weekday)}")


# ------------------------------------------
# 🔹 メインメニュー
# ------------------------------------------
def main() -> None:
    """メニュー表示"""
    manager = AlarmManager()

    def run_alarm_monitor(manager: AlarmManager) -> None:
        """アラーム監視ループを開始する（CUI補助）"""
        print("🔁 アラーム監視開始（Ctrl+Cで停止）")
        try:
            manager.run()
        except KeyboardInterrupt:
            manager.driving_stop()

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
        result: list[int] | None = normalize_weekday_list(raw)
        return result if result is not None else []

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

                date_str: str = input_with_mode(
                    "日付 (YYYY-MM-DD、省略可)", mode="half"
                )
                if not validate_date(date_str):
                    print("年月日の値が不適合です。")
                    continue
                time_str: str = input_with_mode("時刻 (HH:MM)", mode="half")
                if not validate_time(time_str):
                    print("時刻の値が不適合です。")
                    continue

                repeat: str = input_repeat()
                weekday: list[int] = []
                week_of_month: list[int] = []
                interval_weeks = 1

                if repeat == "weekly":
                    weekday = input_weekday_list()
                    interval_weeks = int(
                        input_with_mode(
                            "間隔(週)（デフォルト1）", mode="half", default="1"
                        )
                    )

                elif repeat == "custom":
                    weekday = input_weekday_list()
                    week_of_month = input_week_of_month()
                    interval_weeks = int(
                        input_with_mode(
                            "間隔(週)（デフォルト1）", mode="half", default="1"
                        )
                    )

                sound_input: str = input_with_mode(
                    "音ファイル名 (default.wav、省略可、'select'で選択)",
                    mode="half",
                    default=str(DEFAULT_SOUND),
                )
                if sound_input.lower() == "select":
                    sound: str = select_sound_file()
                elif sound_input == "":
                    sound = str(DEFAULT_SOUND)
                else:
                    sound: str = sound_input

                try:
                    duration = int(
                        input_with_mode("鳴動時間(秒)", mode="half", default="10")
                    )
                except (ValueError, TypeError):
                    duration = 5

                skip_holiday: bool = input_bool("祝日スキップしますか", default=False)
                try:
                    snooze_limit = int(
                        input_with_mode(
                            "スヌーズ上限(回、デフォルト3)", mode="half", default="3"
                        )
                    )
                except (ValueError, TypeError):
                    snooze_limit = 3

                ui_alarm = AlarmUI(
                    name=name,
                    date=date_str,
                    time=time_str,
                    repeat=repeat,
                    weekday=weekday,
                    week_of_month=week_of_month,
                    interval_weeks=interval_weeks,
                    enabled=True,
                    sound=str(sound),
                    skip_holiday=skip_holiday,
                    duration=duration,
                    snooze_minutes=manager.snooze_default,
                    snooze_limit=snooze_limit,
                )

                ui_state = AlarmStateUI(
                    _snoozed_until=None,  # スヌーズ解除予定時刻
                    _snooze_count=0,  # 現在のスヌーズ回数
                    _triggered=False,  # 現在鳴動中かどうか
                    _triggered_at=None,  # 鳴動開始時刻
                    _last_fired_at=None,  # 最後に鳴動した時刻（多重発火防止用）
                )

                internal_alarm: AlarmInternal = ui_to_internal(ui_alarm)
                internal_state: AlarmStateInternal = stateui_to_stateinternal(ui_state)

                # 呼び出し時のシグネチャ差異に強靭に対応する（静的解析のエラー回避および複数実装の互換性）
                add_fn = getattr(manager, "add_alarm", None)
                if callable(add_fn):
                    try:
                        add_fn(json_alarm, json_state)
                    except TypeError:
                        try:
                            add_fn(json_alarm=json_alarm, json_state=json_state)
                        except TypeError:
                            # 追加の名前候補にフォールバック
                            if hasattr(manager, "add_alarm_from_json"):
                                manager.add_alarm_from_json(json_alarm, json_state)
                            elif hasattr(manager, "add_from_json"):
                                manager.add_from_json(json_alarm, json_state)
                            else:
                                raise
                else:
                    raise AttributeError(
                        "AlarmManager has no callable 'add_alarm' method"
                    )

            except KeyboardInterrupt:
                print("入力をキャンセルしました。メニューに戻ります。")

        elif choice == "2":
            print_upcoming_alarms(manager)

        elif choice == "3":
            alarm_id = int(input("削除するID: "))
            manager.remove_alarm(alarm_id)

        elif choice == "4":
            alarm_id = int(input("切替するID: "))
            manager.toggle_alarm(alarm_id)

        elif choice == "5":
            run_alarm_monitor(manager)

        elif choice == "0":
            print("終了します。")
            break

        else:
            print("無効な選択です。")


if __name__ == "__main__":
    main()
