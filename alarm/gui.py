# -*- coding: utf-8 -*-
# pylint: disable=C0415,W0718,C0302,C0301,W0201
"""GUI駆動の表示、データ入出力のみを担当します"""
#########################
# Author: F.Kurokawa
# Description:
# GUIscript
#########################
# gui.py は AlarmGUI / AlarmStateGUI しか触らない
from __future__ import annotations
# --- Python標準ライブラリ -------------------------------------------------
import math
import os

# --- Tkinter関連 ------------------------------------------------------------
from pathlib import Path
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Callable, Literal, TypedDict, cast

from alarm.alarm_config_manager import Config, ConfigManager
from alarm.alarm_ui_model import AlarmDisplayRow, AlarmUI, AlarmUIPatch
from alarm.custom_repeat_dialog import CustomRepeatDialog
from alarm.weekday_select_dialog import WeekdaySelectDialog
from alarm.window_position_store import WindowPositionStore

# --- 自作モジュール ---------------------------------------------------------
from alarm.constants import (
    COLUMN_BASE,
    COLUMN_LABELS,
    DEFAULT_SOUND,
    REPEAT_DISPLAY,
    REPEAT_INTERNAL,
    REPEAT_OPTIONS_GUI,
    WEEKDAY_LABELS,
    DEFAULT_DURATION_SECONDS,
    DEFAULT_SNOOZE_MINUTES,
)
from alarm.cui_datetime_normalizer import validate_date, validate_time
from alarm.logger_bridge import AlarmLogger, get_alarm_logger
from alarm.weekday_formatter import weekday_to_str
from alarm.window_keys import WindowKey
from utils.text_utils import to_hankaku

WINDOW_KEYS: dict[str, WindowKey] = {
    "MAIN": WindowKey.MAIN,
    "SETTINGS": WindowKey.SETTINGS,
    "WEEKDAY": WindowKey.WEEKDAY,
    "CUSTOM": WindowKey.CUSTOM,
    "CALENDAR": WindowKey.CALENDAR,
    "TIME": WindowKey.TIME,
}

# print(python_version := os.sys.version) # デバッグ用
if TYPE_CHECKING:
    from alarm.gui_controller import GUIController


class CustomRepeatData(TypedDict):
    """GUI内で保持するカスタム繰り返し設定。"""

    weekday: list[int]
    week_of_month: list[int]
    interval_weeks: int


# =========================================================
# 🔹 GUIクラス（AlarmManagerと連携）
# =========================================================
class AlarmGUI:
    """GUI駆動・コントロールクラス"""
    main_frame: tk.Frame
    date_label: tk.Label
    time_label: tk.Label
    next_label: tk.Label
    snooze_status_label: tk.Label
    stop_button: tk.Button
    snooze_button: tk.Button
    snooze_entry: tk.Entry
    tree: ttk.Treeview
    settings_window: tk.Toplevel
    name_entry: ttk.Entry
    date_entry: ttk.Entry
    time_entry: ttk.Entry
    repeat_combo: ttk.Combobox
    custom_btn: ttk.Button
    weekday_btn: ttk.Button
    skip_holiday_combo: ttk.Combobox
    snooze_limit_combo: ttk.Combobox
    sound_entry: ttk.Entry
    custom_data: CustomRepeatData | None
    weekday_selected: list[int]
    _refreshing_tree: bool
    # =========================================
    # 🔹 __init__
    # =========================================
    def __init__(self, controller: "GUIController") -> None:
        self.controller: "GUIController" = controller
        self.logger: AlarmLogger = get_alarm_logger()
        self.root = tk.Tk()
        # Tk after 版のプレーヤーを使用
        from alarm.alarm_player import AlarmPlayerGUI
        from alarm.alarm_storage import AlarmStorage

        self.player = AlarmPlayerGUI(self.root)
        self.storage = AlarmStorage()
        self.config_manager = ConfigManager()
        self.config_data: Config = self.config_manager.load_config()
        self._next_alarm_cache: tuple[datetime, AlarmUI] | tuple[None, None] = (None, None)
        self._next_label_line1: str = ""
        self._current_alarm_id: str | None = None
        self._refreshing_tree = False
        # =========================================
        self.window_position_store = WindowPositionStore()
        # ============UI_data==========
        self.alarm_ui_list: list[AlarmUI] = self.controller.get_all_alarm_uis()
        self.alarm_ui: AlarmUI | None = None

        # 🟢 ① まず位置復元を試みる
        restored: bool = False
        if hasattr(self.controller.manager, "window_position_store"):
            restored = self.window_position_store.load_window_position(
                self.root,
                WINDOW_KEYS["MAIN"]
                )
        if not restored:
            # ⭐ 初回起動 → 左上に固定
            self.root.geometry("520x400+40+40")
        else:
            # ⭐ 復元されているのでサイズだけ設定
            self.root.geometry("520x400")

        self.root.resizable(True, True)
        self.root.title("アラームクロック")

        # 🟢 ② 閉じる動作
        self.root.protocol("WM_DELETE_WINDOW", self.on_main_close)

        # 🟢 ③ メニュー／メインUIの構築
        self.create_menu()
        self.create_main_widgets()

        # 🟢 ④ リスナー
        self.controller.manager.add_listener(self._refresh_tree_listener)

    def _refresh_tree_listener(self) -> None:
        """Manager listener 用の no-arg ラッパー。"""
        self.refresh_tree()

    def _log_ui_warning(self, message: str, **context: object) -> None:
        """GUI の warning を context 付きで残す。"""
        self.logger.warning(message, context=context)

    def _log_ui_error(self, message: str, error: Exception, **context: object) -> None:
        """GUI の error を context 付きで残す。"""
        self.logger.error(
            message,
            context={
                "error": repr(error),
                "error_type": type(error).__name__,
                **context,
            },
        )

    def _autosize_tree_columns(self) -> None:
        """Treeview の列幅を見出しと内容の長さに合わせて調整する。"""
        tree: ttk.Treeview | None = getattr(self, "tree", None)
        if tree is None or not tree.winfo_exists():
            return

        columns: tuple[str, ...] = cast(tuple[str, ...], tree["columns"])
        rows: list[tuple[str, ...]] = [
            tuple(str(value) for value in tree.item(item_id, "values"))
            for item_id in tree.get_children()
        ]

        for col_index, col_name in enumerate(columns):
            header_text: str = COLUMN_LABELS.get(col_name, col_name)
            candidates: list[str] = [header_text]
            for row in rows:
                if col_index < len(row):
                    candidates.append(row[col_index])

            max_len: int = max((len(text) for text in candidates), default=0)
            if col_name == "custom_desc":
                max_len = max(max_len, 24)
                width: int = min(max(max_len * 8, 180), 420)
            elif col_name in ("name", "date", "time", "repeat", "weekday"):
                width = min(max(max_len * 10, 90), 220)
            elif col_name in ("snooze_limit", "duration", "enabled", "skip_holiday"):
                width = min(max(max_len * 10, 80), 150)
            else:
                width = min(max(max_len * 9, 80), 240)

            tree.column(col_name, width=width, stretch=True)

    # --------------------------------------------
    # 🔹 messagebox ラッパー（親をメインに固定）
    # --------------------------------------------
    def _info(self, title: str, msg: str, parent: tk.Misc | None = None) -> str:
        owner: tk.Misc = self.root if parent is None else parent
        return messagebox.showinfo(title, msg, parent=owner)

    def _warn(self, title: str, msg: str, parent: tk.Misc | None = None) -> str:
        owner: tk.Misc = self.root if parent is None else parent
        return messagebox.showwarning(title, msg, parent=owner)

    def _error(self, title: str, msg: str, parent: tk.Misc | None = None) -> str:
        owner: tk.Misc = self.root if parent is None else parent
        return messagebox.showerror(title, msg, parent=owner)

    def _ask_yes_no(self, title: str, msg: str, parent: tk.Misc | None = None) -> bool:
        owner: tk.Misc = self.root if parent is None else parent
        return messagebox.askyesno(title, msg, parent=owner)

    # --------------------------------------------
    # 🔹 ウインド位置記憶
    # --------------------------------------------
    def get_window_pos_file(self) -> str:
        """GUI 側へ config.json の場所だけを渡す。"""
        base: Path = self.controller.manager.base_dir
        return os.path.join(base, "config.json")

    def save_window_position(self, window: tk.Misc, key: WindowKey) -> None:
        """ウインド位置を保存する。"""
        if not isinstance(window, (tk.Tk, tk.Toplevel)):
            self._log_ui_warning(
                "Skipped saving non-window widget position",
                window_key=key,
                window_type=type(window).__name__,
            )
            return

        try:
            self.window_position_store.save_window_position(window, key)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._log_ui_error(
                "Failed to save window position",
                e,
                window_key=key,
                window_type=type(window).__name__,
            )
            print("⚠ ウインド位置の保存失敗:", e)

    def load_window_position(self, window: tk.Misc, key: WindowKey) -> bool:
        """保存されたウインド位置を復元する。
        復元に成功すれば True、位置が無ければ False を返す。
        """
        if not isinstance(window, (tk.Tk, tk.Toplevel)):
            self._log_ui_warning(
                "Skipped loading non-window widget position",
                window_key=key,
                window_type=type(window).__name__,
            )
            return False

        try:
            return self.window_position_store.load_window_position(window, key)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._log_ui_error(
                "Failed to load window position",
                e,
                window_key=key,
                window_type=type(window).__name__,
            )
            print(f"[WARN] load_window_position エラー: {e}")
            return False

    # --------------------------------------------
    # 🔹 GUI起動
    # --------------------------------------------
    def start_gui(self) -> None:
        """GUIのメインループ開始"""
        # ✅ GUIが立ってからループ開始
        # 位置復元（★ window = self.root を渡す）
        self.window_position_store.load_window_position(self.root, WINDOW_KEYS["MAIN"])
        # NOTE:
        # まず時計を描画してから、重めの Manager 系ループを少し遅らせて開始する。
        self.update_clock()
        self.root.after(1200, self.alarm_check_loop)
        self.root.after(2000, self.next_alarm_update_loop)  # 次アラーム表示は定期更新
        self.root.after(1500, self._countdown_loop)  # 残り時間のみの更新
        self.root.mainloop()

    # --------------------------------------------
    # 🔹 時計表示更新（UIのみ）
    # --------------------------------------------
    def update_clock(self) -> None:
        """時計表示更新（UIのみ）"""
        now: datetime = datetime.now()
        # now = datetime.now() のあとに追加
        weekday_jp: str = WEEKDAY_LABELS[now.weekday()]  # 月=0 → "月"
        # 表示
        self.date_label.config(text=now.strftime(f"%Y年%m月%d日（{weekday_jp}）"))
        self.time_label.config(text=now.strftime("%H:%M:%S"))
        self.root.after(1000, self.update_clock)

    # --------------------------------------------
    # 🔹 アラーム鳴動チェック（音鳴らし）
    # --------------------------------------------
    def alarm_check_loop(self) -> None:
        """アラーム鳴動チェック（音鳴らし）"""
        try:
            self.controller.run_alarm_cycle()
            self.update_next_alarm_label(recalc=True)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._log_ui_error(
                "alarm_check_loop failed",
                e,
                next_alarm_cache=self._next_alarm_cache,
                manager_alarm_count=len(getattr(self.controller.manager, "alarms", [])),
            )
            print(f"[WARN] alarm_check_loop エラー: {e}")

        self.root.after(1000, self.alarm_check_loop)

    def _finish_alarm(self) -> None:
        """鳴動終了時にフラグと表示をリセット"""
        # 背景と表示を通常に戻す
        self._set_bg_normal()
        self.update_next_alarm_label(recalc=True)

    # --------------------------------------------
    # 🔹 「次のアラーム」表示更新（30秒ごと）
    # --------------------------------------------
    def next_alarm_update_loop(self) -> None:
        """重い計算はここだけで定期的に実施"""
        self.update_next_alarm_label(recalc=True)
        self.root.after(30000, self.next_alarm_update_loop)  # 30秒ごとに再計算

    # --------------------------------------------
    # 🔹 次のアラーム表示本体（既存のやつ・修正版）
    # --------------------------------------------
    def update_next_alarm_label(self, recalc: bool = True) -> None:
        """次のアラームを再計算しキャッシュ。残り時間は別ループで更新。"""
        if recalc:
            # まず鳴動中・スヌーズ中のアラームを優先表示
            current: AlarmUI | None = self.controller.get_active_alarm_ui()
            if current and current.id and self.controller.is_alarm_triggered(current.id):
                alarm: AlarmUI = current
                next_time_calc: datetime = datetime.now()
                icon = "🔔"
                self._set_bg_triggered()
                name: str = alarm.name or "(名称なし)"
                repeat_display: str = REPEAT_DISPLAY.get(
                    alarm.repeat or "none", alarm.repeat or ""
                )
                weekday_list: list[int] = list(alarm.weekday or [])  # type: ignore
                weekday_str: str = weekday_to_str(weekday_list) if weekday_list else ""

                line1: str = f"{icon} 鳴動中：{name}"
                if repeat_display:
                    line1 += f" / {repeat_display}"
                if weekday_str:
                    line1 += f"（{weekday_str}）"

                self._next_alarm_cache = (next_time_calc, alarm)
                self._next_label_line1 = line1
            else:
                try:
                    next_alarm: tuple[datetime, AlarmUI] | None = self.controller.get_next_alarm_ui()
                    # print(f"call_time: {datetime.now().strftime('%M:%S')}")
                except ValueError as e:
                    self._log_ui_warning(
                        "Failed to get next alarm for label update",
                        error=repr(e),
                        error_type=type(e).__name__,
                        next_alarm_cache=self._next_alarm_cache,
                    )
                    print(f"[WARN] 次のアラーム取得でエラー: {e}")
                    next_alarm = None

                next_time: datetime | None

                if next_alarm is None:
                    self._next_alarm_cache = (None, None)
                    self._next_label_line1 = "⏰ 次のアラーム：なし"
                    self._set_bg_normal()
                    self.next_label.config(text=self._next_label_line1, fg="#14325C")
                    self.snooze_status_label.config(text="")
                    self._set_alarm_action_state(is_active=False, is_snoozed=False)
                    return

                next_time, alarm = next_alarm
                next_time_calc = next_time

                # スヌーズ中
                snoozed_until: datetime | None = (
                    self.controller.get_snoozed_until(alarm.id) if alarm.id else None
                )
                if snoozed_until is not None:
                    next_time_calc = snoozed_until
                    icon = "😴"
                    self._set_bg_snooze()
                else:
                    icon = "⏰"
                    self._set_bg_normal()

                name: str = alarm.name or "(名称なし)"
                repeat_display: str = REPEAT_DISPLAY.get(
                    alarm.repeat or "none", alarm.repeat or ""
                )
                weekday_list: list[int] = [d for d in (alarm.weekday or []) if isinstance(d, int)]
                weekday_str = weekday_to_str(weekday_list) if weekday_list else ""

                line1: str = (
                    f"{icon} 次のアラーム：{name} {next_time_calc.strftime('%H:%M')}"
                )
                if repeat_display:
                    line1 += f" / {repeat_display}"
                if weekday_str:
                    line1 += f"（{weekday_str}）"

                self._next_alarm_cache = (next_time_calc, alarm)
                self._next_label_line1: str = line1
                self._current_alarm_id = alarm.id
                if snoozed_until is not None:
                    active_alarm: AlarmUI | None = self.controller.get_active_alarm_ui()
                    self._sync_snooze_minutes_from_alarm(active_alarm or alarm)
                else:
                    self._sync_snooze_minutes_from_alarm(alarm)
                self._update_snooze_status_line(alarm, snoozed_until)

        self._update_remaining_text()

    def _update_snooze_status_line(
        self,
        alarm: AlarmUI | None,
        snoozed_until: datetime | None,
    ) -> None:
        """スヌーズ時の補助情報を次のアラームの下へ表示する。"""
        if alarm is None or snoozed_until is None:
            self.snooze_status_label.config(text="")
            return

        remaining_seconds: int = max(
            0, int((snoozed_until - datetime.now()).total_seconds())
        )
        remaining_minutes: int = math.ceil(remaining_seconds / 60)

        if remaining_minutes >= 60:
            hours: int = remaining_minutes // 60
            minutes: int = remaining_minutes % 60
            detail: str = f"スヌーズ: {snoozed_until.strftime('%H:%M')} / あと {hours} 時間 {minutes} 分"
        else:
            detail: str = f"スヌーズ: {snoozed_until.strftime('%H:%M')} / あと {remaining_minutes} 分"

        self.snooze_status_label.config(text=detail)

    def _sync_snooze_minutes_from_alarm(self, alarm: AlarmUI | None) -> None:
        """表示対象のアラームからスヌーズ分数を入力欄へ反映する。"""
        if alarm is None:
            return
        if self.snooze_entry.focus_get() is self.snooze_entry:
            return

        try:
            snooze_minutes: int = int(alarm.snooze_minutes)
        except Exception:
            snooze_minutes = self.controller.get_snooze_default_minutes()

        self.snooze_entry.delete(0, tk.END)
        self.snooze_entry.insert(0, str(snooze_minutes))

    def _set_alarm_action_state(self, *, is_active: bool, is_snoozed: bool) -> None:
        """STOP と スヌーズ の見た目を状態に応じて切り替える。"""
        if is_active or is_snoozed:
            self.stop_button.config(
                state="normal",
                bg="#ff5a5f" if is_active else "#f6a500",
                activebackground="#ff7a7a" if is_active else "#ffc94d",
                fg="white",
                activeforeground="white",
            )
            self.snooze_button.config(
                state="normal",
                bg="#ff9800" if is_snoozed else "#4d9fe8",
                activebackground="#ffb347" if is_snoozed else "#74b9ff",
                fg="white",
                activeforeground="white",
            )
        else:
            self.stop_button.config(
                state="disabled",
                bg="#f2c7c7",
                activebackground="#f2c7c7",
                fg="#7a7a7a",
                activeforeground="#7a7a7a",
                disabledforeground="#7a7a7a",
            )
            self.snooze_button.config(
                state="disabled",
                bg="#d7e6f5",
                activebackground="#d7e6f5",
                fg="#7a7a7a",
                activeforeground="#7a7a7a",
                disabledforeground="#7a7a7a",
            )

    def _update_remaining_text(self) -> None:
        """キャッシュをもとに残り時間のみ更新"""
        if not self._next_alarm_cache:
            self.next_label.config(text="⏰ 次のアラーム：なし", fg="#14325C")
            self.snooze_status_label.config(text="")
            self._set_bg_normal()
            self._set_alarm_action_state(is_active=False, is_snoozed=False)
            return

        next_time_calc: datetime | None
        alarm: AlarmUI | None

        next_time_calc, alarm = self._next_alarm_cache

        if alarm and alarm.id and self.controller.is_alarm_triggered(alarm.id):
            self.next_label.config(text=f"{self._next_label_line1}\n鳴動中", fg="#b00020")
            self._set_bg_triggered()
            self._set_alarm_action_state(is_active=True, is_snoozed=False)
            self.snooze_status_label.config(text="")
            return

        # 過去になっていたら再計算
        if next_time_calc is None or next_time_calc < datetime.now():
            self.next_label.config(text=self._next_label_line1, fg="#14325C")
            self._set_bg_normal()
            self._set_alarm_action_state(is_active=False, is_snoozed=False)
            self.snooze_status_label.config(text="")
            return

        diff = int((next_time_calc - datetime.now()).total_seconds())
        if diff <= 15:
            remaining = "まもなく鳴ります"
        else:
            minutes: int = math.ceil(diff / 60)
            if minutes >= 60:
                h: int = minutes // 60
                m: int = minutes % 60
                remaining: str = f"あと {h} 時間 {m} 分"
            elif minutes >= 1:
                remaining: str = f"あと {minutes} 分"
            else:
                remaining: str = "まもなく鳴ります"

        snoozed: bool = alarm is not None and alarm.id is not None and (
            self.controller.get_snoozed_until(alarm.id) is not None
        )
        if snoozed:
            snoozed_until: datetime | None = (
                self.controller.get_snoozed_until(alarm.id) if alarm and alarm.id else None
            )
            self.next_label.config(text=f"{self._next_label_line1}\n{remaining}", fg="#b26a00")
            self._set_bg_snooze()
            self._set_alarm_action_state(is_active=False, is_snoozed=True)
            self._update_snooze_status_line(alarm, snoozed_until)
        else:
            self.next_label.config(text=f"{self._next_label_line1}\n{remaining}", fg="#14325C")
            self._set_bg_normal()
            self._set_alarm_action_state(is_active=False, is_snoozed=False)
            self.snooze_status_label.config(text="")

    def _countdown_loop(self) -> None:
        self._update_remaining_text()
        self.root.after(1000, self._countdown_loop)

    # ---------------------------------------------------------
    # 🔧 Treeview セル内に Entry / Combobox を配置する共通関数
    # ---------------------------------------------------------
    def create_cell_editor(
        self,
        tree: ttk.Treeview,
        item_id: str,
        column_id: str,
        commit_callback: Callable[[str], None]
    ) -> Callable[[tk.Entry | ttk.Combobox], None]:
        """
        Entry / Combobox などのウィジェットを Treeview のセル上に重ねて表示し、
        編集完了後 commit_callback(value) を呼び出す。
        """
        bbox: tuple[int, int, int, int] | Literal[''] = tree.bbox(item_id, column_id)
        if not bbox:
            return lambda widget: None  # type: ignore  # セルが不可視の場合

        x: int
        y: int
        width: int
        height: int

        x, y, width, height = bbox

        def editor_setter(widget: tk.Entry | ttk.Combobox) -> None:
            # 位置とサイズをセルに合わせる
            widget.place(in_=tree, x=x, y=y, width=width, height=height)

            # フォーカスを当てる
            widget.focus_set()

            # 編集完了（Enter）
            def done(_event: tk.Event[tk.Widget] | None = None) -> None:
                value: str = widget.get()
                widget.destroy()
                commit_callback(value)

            # キャンセル（Escape）
            def cancel(_event: tk.Event[tk.Widget] | None = None) -> None:
                widget.destroy()

            widget.bind("<Return>", done)
            widget.bind("<Escape>", cancel)

        return editor_setter

    # ---------------------------------------
    # 🔹 一覧更新（カスタム内容の日本語要約付き）
    # ---------------------------------------
    def refresh_tree(self) -> None:
        """一覧更新（カスタム内容の日本語要約付き）"""
        # NOTE:
        # Manager の listener 通知中に再度 refresh_tree() が入ると、
        # notify -> refresh_tree -> notify の再帰ループへ進む危険がある。
        # Silent Breaking Bugs を避けるため、一覧再描画中の再入は捨てる。
        if getattr(self, "_refreshing_tree", False):
            self._log_ui_warning(
                "Skipped re-entrant refresh_tree",
                tree_exists=hasattr(self, "tree"),
                manager_alarm_count=len(self.controller.get_alarm_display_rows()),
            )
            return

        self._refreshing_tree = True

        try:
            # ✅ TreeView が存在しない場合は終了
            if not hasattr(self, "tree") or not self.tree.winfo_exists():
                return

            self.tree.delete(*self.tree.get_children())

            display_rows: list[AlarmDisplayRow] = self.controller.get_alarm_display_rows()
            for row in display_rows:
                # ID 0（ダミー行など）は一覧に出さない
                try:
                    if not row.alarm_id:
                        continue
                except(ValueError, AttributeError) as e:
                    self._log_ui_warning(
                        "Skipped alarm with invalid id during refresh_tree",
                        alarm_data=row,
                        alarm_type=type(row).__name__,
                        error=repr(e),
                        error_type=type(e).__name__,
                    )
                    continue

                if not row.name:
                    self._log_ui_warning(
                        "Skipped alarm with empty name during refresh_tree",
                        alarm_id=row.alarm_id,
                    )
                # NOTE:
                # 表示用の連番と、更新用の alarm_id を分離する。
                # Treeview の iid に alarm_id を保持し、ID列は row_no のみ表示する。
                display_id: int = row.row_no
                enabled_str: str = "ON" if row.enabled else "OFF"
                skip_str: str = "✔" if row.skip_holiday else "×"
                repeat_display: str = REPEAT_DISPLAY.get(row.repeat, row.repeat)

                # 🔹 表示行を構築
                values: list[str | int] = [
                    display_id,
                    row.name,
                    row.date,
                    row.time,
                    repeat_display,
                    row.weekday,
                    enabled_str,
                    skip_str,
                    row.duration,
                    row.snooze_minutes,
                    row.snooze_limit,
                    row.end_at,
                    row.custom_desc,
                ]
                self.tree.insert("", "end", iid=row.alarm_id, values=values)

            self._autosize_tree_columns()

            # NOTE:
            # 「次のアラーム」表示は next_alarm_update_loop() 側で定期更新する。
            # listener 経由の一覧更新と同じタイミングで Manager 参照を増やすと、
            # notify 連鎖の再帰を呼び戻しやすいため、ここでは同期しない。
        finally:
            self._refreshing_tree = False

    # ------------------------------
    # ⚙ selectメニュー
    # ------------------------------
    def create_menu(self) -> None:
        """メインウインドにメニューを作成する"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        settings_menu = tk.Menu(menubar, tearoff=0)

        # --- create_menu 内だけの簡易ラッパー関数 ---
        def _set_gui() -> None:
            self.config_set_default_mode("gui")

        def _set_cui() -> None:
            self.config_set_default_mode("cui")

        def _dialog_on() -> None:
            self.config_set_dialog_enabled(True)

        def _dialog_off() -> None:
            self.config_set_dialog_enabled(False)

        def _open_json_editor() -> None:
            from alarm.json_editor import JsonEditor

            JsonEditor(
                self.root,
                self.controller.get_alarm_file_path(),
                on_saved=self.controller.reload_after_external_json_edit,
            )

        def _restore_backup() -> None:
            self.storage.restore_latest()

        # GUI/CUI 起動設定
        settings_menu.add_command(
            label="設定ウインドウを開く", command=self.open_settings_window
        )
        settings_menu.add_separator()

        settings_menu.add_command(label="次回は GUI で自動起動", command=_set_gui)
        settings_menu.add_command(label="次回は CUI で自動起動", command=_set_cui)
        settings_menu.add_separator()
        settings_menu.add_command(
            label="起動時に選択ダイアログを表示", command=_dialog_on
        )
        settings_menu.add_command(
            label="起動時のダイアログを非表示", command=_dialog_off
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="JSON 修復エディター", command=_open_json_editor
        )
        settings_menu.add_command(label="バックアップから復元", command=_restore_backup)

        settings_menu.add_separator()
        settings_menu.add_command(label="終了", command=self.root.quit)

        menubar.add_cascade(label="⚙ 設定", menu=settings_menu)

    # --------------------------------------------
    # 🔧 本体（config の変更処理）はクラスメソッドにする
    # --------------------------------------------
    def config_set_default_mode(self, mode: Literal["gui", "cui"]) -> None:
        """デフォルト起動モードを変更"""
        self.config_data.default_mode = mode
        self.config_manager.save_config(self.config_data)
        self._info("設定", f"次回の起動は {mode.upper()} になります")

    def config_set_dialog_enabled(self, flag: bool) -> None:
        """起動モード選択ダイアログの表示設定を変更"""
        self.config_data.show_dialog = flag
        self.config_manager.save_config(self.config_data)

    # --------------------------------------------
    # 🔹 メイン画面構成
    # --------------------------------------------
    def create_main_widgets(self) -> None:
        """メイン画面のウィジェットを作成する"""
        # 🌙 全体背景
        self.main_frame = tk.Frame(self.root, bg="#f0f0f0", padx=20, pady=20)
        self.main_frame.pack(fill="both", expand=True)

        # --- 日付 ---
        self.date_label = tk.Label(
            self.main_frame, font=("Meiryo", 14), bg="#f0f0f0", fg="#333"
        )
        self.date_label.pack(pady=(0, 5))

        # --- 時計 ---
        self.time_label = tk.Label(
            self.main_frame, font=("Meiryo", 46, "bold"), bg="#f0f0f0", fg="#14325C"
        )
        self.time_label.pack(pady=(0, 15))

        # --- 次のアラーム ---
        self.next_label = tk.Label(
            self.main_frame, font=("Meiryo", 14), bg="#f0f0f0", fg="#14325C"
        )
        self.next_label.pack(pady=(0, 20))

        self.snooze_status_label = tk.Label(
            self.main_frame,
            font=("Meiryo", 11),
            bg="#f0f0f0",
            fg="#6a4c00",
        )
        self.snooze_status_label.pack(pady=(0, 14))

        # --- ボタン行 ---
        button_frame = tk.Frame(self.main_frame, bg="#f0f0f0")
        button_frame.pack(pady=10)

        self.stop_button = tk.Button(
            button_frame,
            text="🛑 STOP",
            bg="#ff6666",
            fg="white",
            width=12,
            font=("Meiryo", 11, "bold"),
            command=self.stop_alarm,
        )
        self.stop_button.pack(side="left", padx=10)

        self.snooze_button = tk.Button(
            button_frame,
            text="💤 スヌーズ",
            bg="#66b3ff",
            fg="white",
            width=12,
            font=("Meiryo", 11, "bold"),
            command=self.snooze_alarm,
        )
        self.snooze_button.pack(side="left", padx=10)

        self._set_alarm_action_state(is_active=False, is_snoozed=False)

        # --- スヌーズ入力 ---
        input_frame = tk.Frame(self.main_frame, bg="#f0f0f0")
        input_frame.pack(pady=(10, 0))

        tk.Label(input_frame, text="このアラームのスヌーズ(分):", bg="#f0f0f0").pack(
            side="left", padx=5
        )
        self.snooze_entry = tk.Entry(input_frame, width=6)
        self.snooze_entry.insert(0, str(self.controller.get_snooze_default_minutes()))
        self.snooze_entry.pack(side="left", padx=5)

    # --------------------------------------------
    # 🔹 これは(「メインウインド（root）」専用)が閉じられた時の処理
    # --------------------------------------------
    def on_main_close(self) -> None:
        """メインウインドの終了処理（位置保存 → 終了）"""

        # 1️⃣ ウインド位置を保存
        try:
            self.save_window_position(self.root, WINDOW_KEYS["MAIN"])
        except tk.TclError as e:
            self._log_ui_error(
                "Failed to save main window position on close",
                e,
                window_key=WINDOW_KEYS["MAIN"],
            )
            print(f"[WARN] メイン位置保存でエラー: {e}")

        # 2️⃣ GUIを終了
        self.root.destroy()

    # --------------------------------------------
    # 🔹 背景色変更
    # --------------------------------------------
    def _set_bg_snooze(self) -> None:
        bg = "#fff4c2"  # スヌーズ時の優しい黄色

        self.main_frame.config(bg=bg)
        self.date_label.config(bg=bg)
        self.time_label.config(bg=bg)
        self.next_label.config(bg=bg)
        self.snooze_status_label.config(bg=bg)

    def _set_bg_normal(self) -> None:
        bg = "#f0f0f0"  # 通常時ライトグレー

        self.main_frame.config(bg=bg)
        self.date_label.config(bg=bg)
        self.time_label.config(bg=bg)
        self.next_label.config(bg=bg)
        self.snooze_status_label.config(bg=bg)

    def _set_bg_triggered(self) -> None:
        bg = "#ffe0e0"  # 鳴動中の赤系

        self.main_frame.config(bg=bg)
        self.date_label.config(bg=bg)
        self.time_label.config(bg=bg)
        self.next_label.config(bg=bg)
        self.snooze_status_label.config(bg=bg)

    # --------------------------------------------
    # 🔹 サウンドファイルセレクト
    # --------------------------------------------
    def select_sound_file(self) -> str:
        """音声ファイルを選択して入力欄に反映"""
        file_path: str = filedialog.askopenfilename(
            title="アラーム音を選択してください",
            initialdir=os.path.dirname(DEFAULT_SOUND),
            filetypes=[
                ("WAVファイル", "*.wav"),
                ("MP3ファイル", "*.mp3"),
                ("すべてのファイル", "*.*"),
            ],
        )

        if file_path:
            # ✅ GUI の音入力欄へ反映（sound_entry → self.sound_entry）
            if hasattr(self, "sound_entry"):
                self.sound_entry.delete(0, tk.END)
                self.sound_entry.insert(0, file_path)

            self._log_ui_warning(
                "Sound file selected from GUI",
                file_path=file_path,
                file_path_type=type(file_path).__name__,
            )
            print(f"🎵 選択されたファイル: {file_path}")
            return file_path

        self._log_ui_warning("Sound file selection canceled", selected_file=None)
        print("⚠️ ファイルが選択されませんでした。デフォルト音を使用します。")
        return str(DEFAULT_SOUND)

    # =========================================================
    # 📌 ウインド位置ユーティリティ（全ウインド共通）
    # =========================================================

    def place_window_near_parent(self, parent: tk.Widget, child: tk.Toplevel, offset_x: int = 40, offset_y: int = 40) -> None:
        """
        親ウインドの右横に配置する（基本）
        parent: 親ウインド
        child: 子ウインド（Toplevel）
        """
        try:
            parent.update_idletasks()
            px: int = parent.winfo_x()
            py: int = parent.winfo_y()
            pw: int = parent.winfo_width()

            # 親の右側に表示（画面外に出ないよう補正）
            x: int = px + pw + offset_x
            y: int = py + offset_y

            child.geometry(f"+{x}+{y}")

        except tk.TclError as e:
            self._log_ui_error(
                "Failed to place window near parent",
                e,
                parent_type=type(parent).__name__,
                child_type=type(child).__name__,
            )
            print(f"[WARN] place_window_near_parent エラー: {e}")

    # ---------------------------------------
    # ✅ 設定ウインド・編集ウインドなど“サブウインド（Toplevel）” を閉じるときの処理。
    # ---------------------------------------
    def on_close(self, win: tk.Toplevel, key: WindowKey) -> None:
        """あらゆるウインドで使える共通クローズ処理"""

        # ① 位置保存
        try:
            self.save_window_position(win, key)
        except Exception as e: # pylint: disable=broad-exception-caught
            self._log_ui_error(
                "Failed to save child window position",
                e,
                window_key=key,
                window_type=type(win).__name__,
            )
            print(f"[WARN] ウインド位置保存失敗 ({key}): {e}")

        # ② 使っていたリスナーがあれば解除
        try:
            self.controller.remove_gui_listener(self._refresh_tree_listener)
        except Exception as e: # pylint: disable=broad-exception-caught
            self._log_ui_error(
                "Failed to remove listener",
                e,
                listener_type=type(self._refresh_tree_listener).__name__,
            )
            print(f"[WARN] リスナー解除失敗: {e}")

        # ③ ウインド破棄
        win.destroy()

    # --------------------------------------------
    # 🔹 設定メニュー（アラーム一覧・登録）
    # --------------------------------------------
    def open_settings_window(self) -> None:
        """設定ウインドを開く"""
        win = tk.Toplevel(self.root)
        self.settings_window: tk.Toplevel = win  # ← 追加！！
        win.title("アラーム設定")
        win.geometry("1320x830")
        win.minsize(1080, 830)
        win.resizable(True, True)

        # --------------------------------------
        # ① ここで UI を全部作る！ ← 超重要！！
        # --------------------------------------

        list_section = ttk.Frame(win)
        list_section.pack(fill="x", padx=10, pady=(10, 0))

        # 見出し
        ttk.Label(list_section, text="登録アラーム一覧", font=("Meiryo", 12, "bold")).pack(
            pady=10
        )

        # Treeview
        columns: tuple[str, ...] = COLUMN_BASE
        self.tree = ttk.Treeview(
            list_section,
            columns=COLUMN_BASE,
            selectmode="extended",
            show="headings",
            height=8,
        )

        for col in columns:
            self.tree.heading(col, text=COLUMN_LABELS.get(col, col))
            self.tree.column(col, width=90, anchor="center")

        self.tree.column("snooze_limit", width=90, anchor="center")
        self.tree.column("custom_desc", width=180, anchor="w")
        self.tree.pack(fill="x", expand=False, padx=10, pady=10)
        self.tree.bind("<Button-1>", self._toggle_tree_selection, add="+")
        self.tree.bind("<Double-1>", self.on_double_click)

        # ここに削除ボタン
        ttk.Button(
            list_section, text="選択アラームを削除", command=self.delete_selected_alarms
        ).pack(pady=(0, 10))

        # ---------------------------------------
        # 🔹 新規登録フォーム（2カラム美しい版）
        # ---------------------------------------
        form: ttk.LabelFrame = ttk.LabelFrame(win, text="新規アラーム登録", padding=12)
        form.pack(fill="x", padx=20, pady=15)

        # グリッド列の設定
        # 0: 左ラベル（固定）
        # 1: 左入力欄（伸ばす）
        # 2: カスタムボタン
        # 3: 右ラベル（固定）
        # 4: 右入力欄（伸ばす）
        # 5: ボタン類
        form.columnconfigure(0, weight=0)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=0)
        form.columnconfigure(3, weight=0)
        form.columnconfigure(4, weight=1)
        form.columnconfigure(5, weight=0)

        padx = (6, 6)
        pady = 4

        # 左列
        ttk.Label(form, text="アラーム名：").grid(
            row=0, column=0, sticky="e", padx=padx, pady=pady
        )
        self.name_entry = ttk.Entry(form)
        self.name_entry.grid(row=0, column=1, sticky="we", padx=padx, pady=pady)

        ttk.Label(form, text="日付：").grid(
            row=1, column=0, sticky="e", padx=padx, pady=pady
        )
        self.date_entry = ttk.Entry(form, state="readonly")
        self.date_entry.grid(row=1, column=1, sticky="w", padx=padx, pady=pady)
        # クリックしたらカレンダー表示
        self.date_entry.bind("<Button-1>", lambda e: self.pick_date())

        ttk.Label(form, text="時刻：").grid(
            row=2, column=0, sticky="e", padx=padx, pady=pady
        )
        self.time_entry = ttk.Entry(form, state="readonly", width=10)
        self.time_entry.grid(row=2, column=1, sticky="w", padx=padx, pady=pady)
        # クリックで時刻ピッカー
        self.time_entry.bind("<Button-1>", lambda e: self.pick_time())

        # 繰り返し
        ttk.Label(form, text="繰り返し：").grid(
            row=3, column=0, sticky="e", padx=padx, pady=pady
        )
        self.repeat_combo = ttk.Combobox(
            form, values=REPEAT_OPTIONS_GUI, width=12, state="readonly"
        )
        self.repeat_combo.current(0)
        self.repeat_combo.grid(row=3, column=1, sticky="w", padx=padx, pady=pady)
        self.repeat_combo.bind("<<ComboboxSelected>>", lambda e: self.on_repeat_change())

        # カスタムボタン
        self.custom_btn = ttk.Button(
            form,
            text="詳細設定",
            width=10,
            state="disabled",
            command=self.open_custom_from_form,
        )
        self.custom_btn.grid(row=3, column=2, sticky="w", padx=padx, pady=pady)
        self.custom_data = None  # カスタム設定の保持用

        # 右列
        ttk.Label(form, text="曜日：").grid(
            row=0, column=3, sticky="e", padx=padx, pady=pady
        )
        self.weekday_selected: list[int] = []
        self.weekday_btn = ttk.Button(
            form, text="選択", width=8, command=self.pick_weekday
        )
        self.weekday_btn.grid(row=0, column=4, sticky="w", padx=padx, pady=pady)

        ttk.Label(form, text="祝日スキップ：").grid(
            row=1, column=3, sticky="e", padx=padx, pady=pady
        )
        self.skip_holiday_combo = ttk.Combobox(
            form, values=["×", "〇"], width=6, state="readonly"
        )
        self.skip_holiday_combo.current(0)
        self.skip_holiday_combo.grid(row=1, column=4, sticky="w", padx=padx, pady=pady)

        ttk.Label(form, text="再生秒数：").grid(
            row=2, column=3, sticky="e", padx=padx, pady=pady
        )
        self.duration_entry = ttk.Entry(form, width=10)
        self.duration_entry.grid(row=2, column=4, sticky="w", padx=padx, pady=pady)
        self.duration_entry.insert(0, str(DEFAULT_DURATION_SECONDS))

        ttk.Label(form, text="Snooze間隔(分)：").grid(
            row=3, column=3, sticky="e", padx=padx, pady=pady
        )
        self.snooze_minutes_entry = ttk.Entry(form, width=10)
        self.snooze_minutes_entry.grid(row=3, column=4, sticky="w", padx=padx, pady=pady)
        self.snooze_minutes_entry.insert(0, str(DEFAULT_SNOOZE_MINUTES))

        ttk.Label(form, text="スヌーズ上限：").grid(
            row=4, column=3, sticky="e", padx=padx, pady=pady
        )
        self.snooze_limit_combo = ttk.Combobox(
            form, values=[str(x) for x in range(1, 7)], width=6, state="readonly"
        )
        self.snooze_limit_combo.current(2)
        self.snooze_limit_combo.grid(row=4, column=4, sticky="w", padx=padx, pady=pady)

        # 音ファイル
        ttk.Label(form, text="音ファイル：").grid(
            row=5, column=3, sticky="e", padx=padx, pady=pady
        )
        self.sound_entry = ttk.Entry(form)
        self.sound_entry.grid(row=5, column=4, sticky="we", padx=padx, pady=pady)
        ttk.Button(
            form,
            text="選択",
            command=lambda: self.sound_entry.insert(0, filedialog.askopenfilename()),
        ).grid(row=5, column=5, padx=padx, pady=pady)

        ttk.Label(form, text="アラーム終了年月日：").grid(
            row=5, column=0, sticky="e", padx=padx, pady=pady
        )

        self.end_date_entry = ttk.Entry(form, width=12)
        self.end_date_entry.grid(row=5, column=1, sticky="w", padx=padx, pady=pady)

        # 左クリックしたら終了日用カレンダー表示
        self.end_date_entry.bind("<Button-1>", lambda e: self.pick_end_date())

        # ttk.Label(form, text="期限年月日：").grid(
        #     row=5, column=3, sticky="e", padx=padx, pady=pady
        # )
        # self.end_time_entry = ttk.Entry(form, width=8)
        # self.end_time_entry.grid(row=5, column=4, sticky="w", padx=padx, pady=pady)
        # self.end_time_entry.insert(0, "23:59")

        # 登録ボタン
        ttk.Button(
            form, text="アラームを登録", width=20, command=self.add_alarm_action
        ).grid(row=6, column=0, columnspan=6, pady=(14, 5))

        # 画面部品をすべて作り終えてから一覧とラベルを更新する
        self.refresh_tree()
        self._autosize_tree_columns()
        self.root.after_idle(self.update_next_alarm_label)

        # --------------------------------------
        # ② UI作成後に update で描画確定！！
        # --------------------------------------
        win.update_idletasks()

        # --------------------------------------
        # ③ 位置復元（前回の位置）
        # --------------------------------------
        restored: bool = self.load_window_position(win, WINDOW_KEYS["SETTINGS"])

        # --------------------------------------
        # ④ 初回は右横へ移動
        # --------------------------------------
        if not restored:
            self.place_subwindow_near_parent(self.root, win, offset_x=40, offset_y=40)

        # --------------------------------------
        # ⑤ 閉じる処理
        # --------------------------------------
        win.protocol(
            "WM_DELETE_WINDOW", lambda: self.on_close(win, WINDOW_KEYS["SETTINGS"])
        )
    # --------------------------------------
    # alarm 終了日選択
    # --------------------------------------
    def pick_end_date(self) -> None:
        """新規登録フォームの「アラーム終了年月日」クリック時に呼ばれる"""
        old_str: str | None = self.end_date_entry.get() or None
        old_date: date | None = None

        if old_str:
            try:
                old_date = date.fromisoformat(old_str)
            except ValueError:
                old_date = None

        new: date | None = self.select_date_dialog(old_date)
        if new:
            self.end_date_entry.delete(0, tk.END)
            self.end_date_entry.insert(0, str(new))
    # ------------------
    # --- 登録済みアラーム削除ボタン ---
    # ------------------
    def delete_selected_alarms(self) -> None:
        """選択されたアラームをまとめて削除する"""
        selected_items: tuple[str, ...] = self.tree.selection()

        if not selected_items:
            self._warn("警告", "削除する行を選択してください")
            return

        # Treeview の iid に alarm_id を入れているので、そのまま使う
        alarm_ids: list[str] = list(selected_items)

        if not self._ask_yes_no("確認", f"{len(alarm_ids)} 件を削除しますか？"):
            return

        self.controller.delete_alarms_from_ui(alarm_ids)
        self.refresh_tree()
        self.update_next_alarm_label()

    # --------------------------------------------
    # 🔹 新規アラーム登録処理
    # --------------------------------------------
    def add_alarm_action(self) -> None:
        """新規アラーム登録処理"""
        name: str = self.name_entry.get().strip()
        if not name:
            self._warn("入力エラー", "アラーム名が入力されていません。")
            return

        # 📅 日付
        date_raw: str = to_hankaku(self.date_entry.get().strip())
        date_str: str | None = validate_date(date_raw)
        if date_str is None and date_raw != "":
            self._warn("入力エラー", "日付は YYYY-MM-DD の形式で入力してください。")
            return

        # ⏰ 時刻
        time_raw: str = to_hankaku(self.time_entry.get().strip())
        time_str: str | None = validate_time(time_raw)
        if time_str is None:
            self._warn("入力エラー", "時刻は HH:MM の形式で入力してください。")
            return

        # 🔁 繰り返し（内部英語に変換）
        repeat_display: str = self.repeat_combo.get()
        repeat: str = REPEAT_INTERNAL.get(repeat_display, "none")

        # 🗓️ カスタム繰り返し選択
        weekday: list[int] = []
        week_of_month: list[int] = []
        interval_weeks: int = 1

        # ✔ weekly_*（毎週／隔週／3週／4週）の場合
        if repeat.startswith("weekly_"):
            interval_weeks = int(repeat.split("_")[1])
            weekday = self.weekday_selected[:]  # ← ★ここが超重要！

        # ✔ カスタム
        elif repeat == "custom":
            # 既存の custom_data を信頼して使う（登録時に再度ダイアログは開かない）
            result: CustomRepeatData | None = self.custom_data
            if not result:
                self._warn("入力エラー", "カスタム設定を入力してください。")
                return
            weekday = result.get("weekday", [])
            week_of_month = result.get("week_of_month", [])
            interval_weeks = result.get("interval_weeks", 1)

        # 🎌 祝日スキップ
        skip_holiday: bool = self.skip_holiday_combo.get() == "〇"

        # 🔊 音ファイル
        sound: str = self.sound_entry.get().strip()

        duration_raw: str = self.duration_entry.get().strip()
        try:
            duration: int = int(duration_raw)
            if duration <= 0:
                raise ValueError
        except ValueError:
            self._warn("入力エラー", "再生秒数は 1 以上の整数で入力してください。")
            return

        snooze_raw: str = self.snooze_minutes_entry.get().strip()
        try:
            snooze_minutes: int = int(snooze_raw)
            if snooze_minutes <= 0:
                raise ValueError
        except ValueError:
            self._warn("入力エラー", "Snooze間隔(分)は 1 以上の整数で入力してください。")
            return

        end_date_raw: str = to_hankaku(self.end_date_entry.get().strip())
        end_date_str: str | None = validate_date(end_date_raw) if end_date_raw else None
        if end_date_raw and end_date_str is None:
            self._warn("入力エラー", "アラーム期限は YYYY-MM-DD 形式で入力してください。")
            return

        # end_time_raw: str = to_hankaku(self.end_time_entry.get().strip())
        # end_time_str: str | None = validate_time(end_time_raw) if end_date_str else None
        # if end_date_str and end_time_str is None:
        #     self._warn("入力エラー", "期限時刻は HH:MM 形式で入力してください。")
        #     return

        end_at: str | None = None
        if end_date_str :
            end_at = f"{end_date_str}T23:59:59"  # 期限時刻は固定で23:59:59にする

        # 😴 スヌーズ上限
        try:
            snooze_limit: int = int(self.snooze_limit_combo.get())
        except Exception: # type: ignore
            snooze_limit = 3

        ui_alarm = AlarmUI(
            id=None,
            name=name,
            date=date_str or "",
            time=time_str,
            repeat=repeat,
            weekday=[str(w) for w in weekday],
            week_of_month=week_of_month,
            interval_weeks=interval_weeks,
            enabled=True,
            sound=sound,
            skip_holiday=skip_holiday,
            duration=duration,
            snooze_minutes=snooze_minutes,
            snooze_limit=snooze_limit,
            end_at=end_at,
        )

        # ✅ Controller 経由で Manager へ登録
        self.controller.add_alarm_from_ui(ui_alarm)

        # 🌟 表示更新・通知
        self.refresh_tree()
        self.update_next_alarm_label()
        self._info("登録完了", f"「{name}」を登録しました。")

    def _toggle_tree_selection(self, event: tk.Event) -> str | None:
        """Treeview の行をクリックでトグル選択する。"""
        tree: ttk.Treeview = self.tree
        if tree.identify_region(event.x, event.y) != "cell":
            return None

        item_id: str = tree.identify_row(event.y)
        if not item_id:
            return None

        current: tuple[str, ...] = tree.selection()
        if item_id in current:
            next_selection: tuple[str, ...] = tuple(x for x in current if x != item_id)
        else:
            next_selection: tuple[str, ...] = current + (item_id,)

        tree.selection_set(next_selection)
        tree.focus(item_id)
        return "break"

    # =========サブウインドウ・ダイアログ群=========
    # --------------------------------------------
    # 🔧 小ウインド位置ユーティリティ（全ウインド共通)
    # --------------------------------------------
    def place_subwindow_near_parent(
        self,
        parent: tk.Misc,
        child: tk.Toplevel,
        offset_x: int = 20,
        offset_y: int = 40
        ) -> None:
        """小ウインドを親ウインドの右横に表示する"""
        parent.update_idletasks()
        px: int = parent.winfo_x()
        py: int = parent.winfo_y()
        pw: int = parent.winfo_width()

        # 子ウインド位置
        child.update_idletasks()
        x: int = px + pw + offset_x
        y: int = py + offset_y

        child.geometry(f"+{x}+{y}")

    def _dock_child_window(self, child: tk.Toplevel) -> None:
        """サブウインドを設定ウインドの右隣に寄せ、前面・フォーカスを与える"""
        try:
            parent: tk.Misc = getattr(self, "settings_window", self.root)
            self.place_subwindow_near_parent(parent, child)
            child.transient(cast(tk.Tk, parent))
            child.lift()  # pyright: ignore[reportUnknownMemberType]
            child.focus_force()
        except tk.TclError as e:
            self._log_ui_warning(
                "Failed to dock custom dialog",
                error=repr(e),
                error_type=type(e).__name__,
            )

    # --------------------------------------------
    # 🔹 曜日選択ダイアログ（毎週専用）
    # --------------------------------------------
    def select_weekdays_dialog(self, initial: list[int] | None = None) -> list[int] | None:
        """毎週繰り返し用のシンプルな曜日選択ダイアログ"""
        parent: tk.Misc = getattr(self, "settings_window", self.root)
        dialog = WeekdaySelectDialog(
            parent=parent,
            owner=self.root,
            initial=initial,
            load_window_position=self.load_window_position,
            save_window_position=self.save_window_position,
            dock_window=self._dock_child_window,
        )
        return dialog.show()

    # --------------------------------------------
    # 🔹 カスタム繰り返し設定ウインドウ（改良版）
    # --------------------------------------------
    # 【設計ルール】
    # カスタム繰り返しは、
    # ・月内ルール（第n週 + 曜日）
    # ・時系列ルール（n週おき + 曜日）
    # のいずれか一方のみを選択する。
    #
    # 両者は参照基準が異なるため、
    # 同時指定は意味を持たず、UIレベルで禁止する。

    def open_custom_dialog(
        self,
        initial: dict[str, list[int] | int] | None = None
        ) -> dict[str, list[int] | int] | None:
        """第n週／曜日／週おきを設定できるカスタム設定ダイアログ"""
        parent: tk.Misc = getattr(self, "settings_window", self.root)
        dialog = CustomRepeatDialog(
            parent=parent,
            owner=self.root,
            initial=initial,
            load_window_position=self.load_window_position,
            save_window_position=self.save_window_position,
            dock_window=self._dock_child_window,
        )
        return dialog.show()

    # --------------------------------------------
    # 🔹 新規登録フォーム用：曜日選択ハンドラ
    # --------------------------------------------
    def pick_weekday(self) -> None:
        """新規登録フォームの「曜日：選択」ボタンから呼ばれる"""
        result: list[int] | None = self.select_weekdays_dialog(self.weekday_selected)
        if result is not None:
            self.weekday_selected = result
            # （お好みでボタンの表示を変えてもOK）
            # 表示例: "月水金" など
            label: str = "".join(WEEKDAY_LABELS[i] for i in result) or "選択"
            self.weekday_btn.config(text=label)
            # weekly 系を選択中ならカスタム保持も同期しておく
            if self.repeat_combo.get().startswith("毎"):
                repeat_display: str = self.repeat_combo.get()

                repeat_interval_map: dict[str, int] = {
                    "毎週": 1,
                    "隔週": 2,
                    "3週おき": 3,
                    "4週おき": 4,
                    "5週おき": 5,
                    "最終週": 6,
                }

                interval_weeks: int = repeat_interval_map.get(repeat_display, 1)

                self.custom_data = {
                    "weekday": self.weekday_selected[:],
                    "week_of_month": [],
                    "interval_weeks": interval_weeks,
                }

    def on_repeat_change(self) -> None:
        """繰り返しコンボ選択時の挙動を制御"""
        repeat_display: str = self.repeat_combo.get()
        repeat: str = REPEAT_INTERNAL.get(repeat_display, "none")

        # カスタムのみ詳細ボタンを有効化
        if repeat == "custom":
            self.custom_btn.config(state="normal")
            # すぐ設定ダイアログを開く（キャンセル可）
            self.open_custom_from_form()
        else:
            self.custom_btn.config(state="disabled")

    def open_custom_from_form(self) -> None:
        """詳細設定ボタンからカスタムダイアログを開く"""
        initial: CustomRepeatData = self.custom_data or {
            "weekday": self.weekday_selected[:],
            "week_of_month": [],
            "interval_weeks": 1,
        }
        result: dict[str, list[int] | int] | None = self.open_custom_dialog(initial=initial)  # type: ignore[arg-type]
        if result:
            self.custom_data = result  # type: ignore[assignment]
            # ボタンに簡易表示
            weekday_list: list[int] | int = result.get("weekday", [])
            if isinstance(weekday_list, int):
                weekday_list = []
            label: str = "".join(WEEKDAY_LABELS[i] for i in weekday_list) or "詳細設定"
            self.custom_btn.config(text=label, state="normal")

    # ---------------------------------------
    # 🔹 編集操作（ダブルクリック：最新版）
    # ---------------------------------------
    # 完全版 on_double_click（曜日カラム対応版）
    # このコードは gui.py の on_double_click を丸ごと置き換えます。
    # Treeview の "repeat" と "weekday" の両方を編集可能にした完全版です。
    def on_double_click(self, event: tk.Event) -> str:
        """Treeview のセルをダブルクリックしたときの編集処理"""
        tree: ttk.Treeview = self.tree
        if not tree or not tree.winfo_exists():
            return "break"

        region: Literal['heading', 'separator', 'tree', 'cell', 'nothing'] = tree.identify_region(event.x, event.y)
        if region != "cell":
            return "break"

        item_id: str = tree.identify_row(event.y)
        column_id: str = tree.identify_column(event.x)
        if not item_id or column_id == "#0":
            return "break"

        # 行とセルを明示的に選択＆フォーカス（Treeview 標準のダブルクリック挙動を抑止）
        tree.selection_set(item_id)
        tree.focus(item_id)
        tree.focus_set()

        values_raw: object = tree.item(item_id, "values")

        if not isinstance(values_raw, (list, tuple)):
            return "break"

        values: list[Any] = list(values_raw)

        if not values:
            return "break"

        alarm_id: str = item_id

        alarm: AlarmUI | None = self.controller.get_alarm_ui_by_id(alarm_id)
        if alarm is None:
            return "break"

        col_index: int = int(column_id[1:]) - 1
        columns: tuple[str, ...] = cast(tuple[str, ...], tree["columns"])
        if not 0 <= col_index < len(columns):
            return "break"

        col_name: str = columns[col_index]
        old_value: Any = values[col_index]

        def set_editor(widget: tk.Entry | ttk.Combobox, commit_callback: Callable[[str], None]) -> None:
            editor_setter: Callable[[tk.Entry | ttk.Combobox], None] = self.create_cell_editor(
                tree, item_id, column_id, commit_callback
            )
            editor_setter(widget)

        if col_name == "weekday":
            current: list[int] = [int(x) for x in (alarm.weekday or [])]
            weekday_result: list[int] | None = self.select_weekdays_dialog(current)
            if weekday_result is None:
                return "break"
            self.controller.update_alarm_from_ui(
                alarm_id,
                AlarmUIPatch(weekday=cast(list[int | str], weekday_result)),
            )
            self.refresh_tree()
            self.update_next_alarm_label()
            return "break"

        if col_name == "repeat":
            current_internal: str = alarm.repeat or "none"
            current_display: str = REPEAT_DISPLAY.get(current_internal, "単発")

            cb = ttk.Combobox(
                tree, values=list(REPEAT_INTERNAL.keys()), state="readonly"
            )
            cb.set(current_display)

            def commit_repeat(value: str) -> None:
                internal: str = REPEAT_INTERNAL.get(value, "none")
                patch = AlarmUIPatch(
                    repeat=internal,
                    weekday=[],
                    week_of_month=[],
                    interval_weeks=1,
                )

                if internal.startswith("weekly_"):
                    interval_weeks = int(internal.split("_")[1])
                    weekday_ints: list[int] = [int(w) for w in (alarm.weekday or [])]
                    result_weekdays: list[int] | None = self.select_weekdays_dialog(weekday_ints)
                    patch.interval_weeks = interval_weeks
                    patch.weekday = [str(w) for w in result_weekdays] if result_weekdays else []
                elif internal == "custom":
                    weekday_ints_custom: list[int] = [int(w) for w in (alarm.weekday or [])]
                    custom_result: dict[str, list[int] | int] | None = self.open_custom_dialog(
                        initial={
                            "weekday": weekday_ints_custom,
                            "week_of_month": list(alarm.week_of_month or []),
                            "interval_weeks": alarm.interval_weeks or 1,
                        }
                    )
                    if custom_result:
                        patch.weekday = [str(w) for w in (custom_result["weekday"] if isinstance(custom_result["weekday"], list) else [])]
                        patch.week_of_month = custom_result["week_of_month"] if isinstance(custom_result["week_of_month"], list) else []
                        patch.interval_weeks = custom_result["interval_weeks"] if isinstance(custom_result["interval_weeks"], int) else 1

                self.controller.update_alarm_from_ui(alarm_id, patch)
                self.refresh_tree()
                self.update_next_alarm_label()

            set_editor(cb, commit_repeat)
            cb.bind("<<ComboboxSelected>>", lambda e: commit_repeat(cb.get()))
            cb.after(100, lambda: cb.event_generate("<Down>"))
            return "break"

        if col_name == "enabled":
            cb = ttk.Combobox(tree, values=["ON", "OFF"], state="readonly")
            cb.set("ON" if alarm.enabled else "OFF")

            def commit_enabled(value: str) -> None:
                self.controller.update_alarm_from_ui(
                    alarm_id,
                    AlarmUIPatch(enabled= value == "ON"),
                )
                self.refresh_tree()
                self.update_next_alarm_label()

            set_editor(cb, commit_enabled)
            cb.bind("<<ComboboxSelected>>", lambda e: commit_enabled(cb.get()))
            cb.after(100, lambda: cb.event_generate("<Down>"))
            return "break"

        if col_name == "skip_holiday":
            cb = ttk.Combobox(tree, values=["✔", "×"], state="readonly")
            cb.set("✔" if alarm.skip_holiday else "×")

            def commit_skip(value: str) -> None:
                self.controller.update_alarm_from_ui(
                    alarm_id,
                    AlarmUIPatch(skip_holiday=value == "✔"),
                )
                self.refresh_tree()
                self.update_next_alarm_label()

            set_editor(cb, commit_skip)
            cb.bind("<<ComboboxSelected>>", lambda e: commit_skip(cb.get()))
            cb.after(100, lambda: cb.event_generate("<Down>"))
            return "break"

        if col_name == "snooze_limit":
            cb = ttk.Combobox(
                tree,
                values=[str(i) for i in range(1, 31)],
                state="normal",
            )

            if alarm.snooze_limit < 1 or alarm.snooze_limit > 30:
                cb.set("3")
            else:
                cb.set(str(alarm.snooze_limit))

            def commit_snooze(value: str) -> None:
                try:
                    snooze_limit = int(value)
                    if snooze_limit < 1 or snooze_limit > 30:
                        raise ValueError
                except ValueError:
                    self._warn("入力エラー", "スヌーズ回数上限は 1〜30 の整数で入力してください。")
                    return

                self.controller.update_alarm_from_ui(
                    alarm_id,
                    AlarmUIPatch(snooze_limit=snooze_limit),
                )
                self.refresh_tree()
                self.update_next_alarm_label()

            set_editor(cb, commit_snooze)
            cb.bind("<<ComboboxSelected>>", lambda e: commit_snooze(cb.get()))
            cb.after(100, lambda: cb.event_generate("<Down>"))
            return "break"

        if col_name == "duration":
            cb = ttk.Combobox(
                tree,
                values=["5", "10", "15", "20", "25", "30", "45", "60", "120"],
                state="normal",
            )
            cb.set(str(alarm.duration))

            def commit_duration(value: str) -> None:
                try:
                    duration = int(value)
                    if duration <= 0:
                        raise ValueError
                except ValueError:
                    self._warn("入力エラー", "再生秒数は 1 以上の整数で入力してください。")
                    return

                self.controller.update_alarm_from_ui(
                    alarm_id,
                    AlarmUIPatch(duration=duration),
                )
                self.refresh_tree()
                self.update_next_alarm_label()

            set_editor(cb, commit_duration)
            cb.bind("<<ComboboxSelected>>", lambda e: commit_duration(cb.get()))
            cb.after(100, lambda: cb.event_generate("<Down>"))
            return "break"

        if col_name == "date":
            if not alarm.date or not alarm.time:
                return "break"

            old_date: str = alarm.date
            old_date_obj: date | None = None
            try:
                old_date_obj = date.fromisoformat(old_date)
            except ValueError:
                old_date_obj = None
            new_date: date | None = self.select_date_dialog(old_date_obj)
            if not new_date:
                return "break"

            self.controller.update_alarm_from_ui(
                alarm_id,
                AlarmUIPatch(date=str(new_date)),
            )
            self.refresh_tree()
            self.update_next_alarm_label()
            return "break"

        if col_name == "time":
            if not alarm.time:
                return "break"

            old_time: str = alarm.time
            new_time: str | None = self.select_time_dialog(old_time)
            if not new_time:
                return "break"

            self.controller.update_alarm_from_ui(
                alarm_id,
                AlarmUIPatch(time=new_time),
            )
            self.refresh_tree()
            self.update_next_alarm_label()
            return "break"

        if col_name == "custom_desc" and (alarm.repeat or "") == "custom":
            weekday_ints_custom: list[int] = [int(w) for w in (alarm.weekday or [])]
            result_custom: dict[str, list[int] | int] | None = self.open_custom_dialog(
                initial={
                    "weekday": weekday_ints_custom,
                    "week_of_month": list(alarm.week_of_month or []),
                    "interval_weeks": alarm.interval_weeks or 1,
                }
            )
            if not result_custom:
                return "break"

            weekday_value: list[int] | int = result_custom.get("weekday", [])
            week_of_month_value: list[int] | int = result_custom.get("week_of_month", [])
            interval_weeks_value: list[int] | int = result_custom.get("interval_weeks", 1)

            weekday_patch: list[int | str] = [
                int(w) if isinstance(w, str) else w for w in weekday_value
            ] if isinstance(weekday_value, list) else []

            week_of_month_patch: list[int] = (
                week_of_month_value
                if isinstance(week_of_month_value, list)
                else []
            )

            interval_weeks_patch: int = (
                interval_weeks_value
                if isinstance(interval_weeks_value, int)
                else 1
            )

            self.controller.update_alarm_from_ui(
                alarm_id,
                AlarmUIPatch(
                    weekday=weekday_patch,
                    week_of_month=week_of_month_patch,
                    interval_weeks=interval_weeks_patch,
                ),
            )
            self.refresh_tree()
            self.update_next_alarm_label()
            return "break"

        if col_name == "name":
            entry = ttk.Entry(tree)
            entry.insert(0, old_value)

            def commit_text(value: str) -> None:
                self.controller.update_alarm_from_ui(
                    alarm_id,
                    AlarmUIPatch(name=value),
                )
                self.refresh_tree()
                self.update_next_alarm_label()

            set_editor(entry, commit_text)
            return "break"

        # 何も処理しない場合もデフォルト動作は抑止する
        return "break"

    # =================================================================
    # 🔹 年月日用ミニカレンダーのコール(一覧編集用)
    # =================================================================
    def select_date_dialog(self, initial_date: date | None = None) -> date | None:
        """ミニカレンダーを開き、YYYY-MM-DD を返す"""
        from alarm.mini_calendar import MiniCalendar

        cal = MiniCalendar(
            self.root,
            initial_date=initial_date,
            window_key=WINDOW_KEYS["CALENDAR"],
        )
        return cal.show()

    # -----------------------------
    # 🕒 TimePicker 呼び出し関数(一覧編集用)
    # -----------------------------
    def select_time_dialog(self, initial_time: str | None = None) -> str | None:
        """TimePicker を開き "HH:MM" を返す"""
        if not initial_time:
            initial_time = datetime.now().strftime("%H:%M")
        try:
            from alarm.mini_calendar import TimePicker

            tp = TimePicker(
                self.root, initial_time or "07:00", window_key=WINDOW_KEYS["TIME"]
            )
            return tp.show()
        except tk.TclError:
            self._error("Error", "TimePicker を読み込めませんでした")
            return None

    # --------------------------------------------
    # 🔹 ミニカレンダー呼び出し（新規登録用）
    # --------------------------------------------
    def pick_date(self) -> None:
        """新規登録フォームの「日付」クリック時に呼ばれる"""
        old_str: str | None = self.date_entry.get() or None
        old_date: date | None = None
        if old_str:
            try:
                old_date = date.fromisoformat(old_str)
            except ValueError:
                old_date = None
        new: date | None = self.select_date_dialog(old_date)
        if new:
            self.date_entry.config(state="normal")
            self.date_entry.delete(0, tk.END)
            self.date_entry.insert(0, str(new))
            self.date_entry.config(state="readonly")

    # --------------------------------------------
    # 🔹 TimePicker 呼び出し（新規登録用）
    # --------------------------------------------
    def pick_time(self) -> None:
        """新規登録フォームの時刻欄クリックで TimePicker を開く"""
        old: str | None = self.time_entry.get() or None
        new: str | None = self.select_time_dialog(old)
        if new:
            self.time_entry.config(state="normal")
            self.time_entry.delete(0, tk.END)
            self.time_entry.insert(0, new)
            self.time_entry.config(state="readonly")

    # --------------------------------------------
    # 🔹 STOPボタン押下時
    # --------------------------------------------
    def stop_alarm(self) -> None:
        """STOPボタン押下時の処理"""
        if not self.controller.stop_alarm_from_ui():
            self._info("情報", "現在鳴動中のアラームはありません。")
            return

        # ↓ 鳴動中・スヌーズ中、どちらでも通る
        self.player.stop()
        self._set_bg_normal()
        self.update_next_alarm_label()

    # --------------------------------------------
    # 🔹 スヌーズボタン押下時
    # --------------------------------------------
    def snooze_alarm(self) -> None:
        """スヌーズボタン押下時の処理"""
        # スヌーズ時間の取得
        try:
            snooze_min: int = int(self.snooze_entry.get())
            if snooze_min <= 0:
                raise ValueError
        except ValueError:
            snooze_min = self.controller.get_snooze_default_minutes()

        ok: bool
        _alarm_name: str
        next_time: datetime | None

        ok, _alarm_name, next_time = self.controller.snooze_alarm_from_ui(snooze_min)

        if not ok:
            self.snooze_status_label.config(text="")
            return

        self.player.stop()
        self.update_next_alarm_label()
        self._update_snooze_status_line(
            self.controller.get_active_alarm_ui(),
            next_time,
        )
    # --------------------------------------------
    # 🔹 起動
    # --------------------------------------------
    def start(self) -> None:
        """GUI を起動する"""
        self.root.mainloop()


# # =========================================================
# # 🔹 メイン実行
# # =========================================================
# def main() -> None:
#     """`python -m alarm.gui` 用の最小起動入口。"""
#     from alarm.alarm_manager import AlarmManager
#     from alarm.gui_controller import GUIController

#     manager = AlarmManager()
#     controller = GUIController(manager)
#     app = AlarmGUI(controller)

#     # NOTE:
#     # Manager の起動サイクルは mainloop 開始前に同期実行せず、
#     # GUI 表示後に回して初期描画の詰まりを減らす。
#     app.root.after(1000, lambda: manager.start_cycle(condition="startup"))
#     app.start_gui()


# if __name__ == "__main__":
#     main()
