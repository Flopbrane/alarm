# -*- coding: utf-8 -*-
"""GUI駆動の表示、データ入出力のみを担当します"""
# pylint: disable=C0415
#########################
# Author: F.Kurokawa
# Description:
# 　GUI　script
#########################
# gui.py は AlarmGUI / AlarmStateGUI しか触らない
from __future__ import annotations
# --- Python標準ライブラリ -------------------------------------------------
import math
import os

# --- Tkinter関連 ------------------------------------------------------------
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Callable, Literal, LiteralString

from alarm.alarm_config_manager import Config, ConfigManager
from alarm.alarm_ui_model import AlarmUI, AlarmUIPatch
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
    WEEKS_CUSTOM_INTERNAL,
)
from alarm.cui_datetime_normalizer import validate_date, validate_time
from alarm.logger_bridge import get_alarm_logger
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
    from logs.multi_info_logger import AppLogger
# =========================================================
# 🔹 GUIクラス（AlarmManagerと連携）
# =========================================================
class AlarmGUI:
    """GUI駆動・コントロールクラス"""
    main_frame: tk.Frame
    date_label: tk.Label
    time_label: tk.Label
    next_label: tk.Label
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
    custom_data: object | None
    weekday_selected: list[int]
    _refreshing_tree: bool
    # =========================================
    # 🔹 __init__
    # =========================================
    def __init__(self, controller: "GUIController") -> None:
        self.controller: "GUIController" = controller
        self.logger: "AppLogger" = get_alarm_logger()
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
        self._refreshing_tree = False
        # =========================================
        self.window_position_store = WindowPositionStore()

        # 🟢 ① まず位置復元を試みる
        restored: bool = False
        if hasattr(self.controller.manager, "window_position_store"):
            restored = self.window_position_store.load_window_position(self.root, WINDOW_KEYS["MAIN"])
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
        base = self.controller.manager.base_dir
        return os.path.join(base, "config.json")

    def save_window_position(self, window: tk.Misc, key: WindowKey) -> None:
        """ウインド位置を保存する。"""
        try:
            self.window_position_store.save_window_position(window, key)
        except Exception as e:
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
        try:
            return self.window_position_store.load_window_position(window, key)
        except Exception as e:
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

    def _finish_alarm(self, alarm_id: str) -> None:
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
                self._set_bg_snooze()
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
                    self._next_label_line1: str = "⏰ 次のアラーム：なし"
                    self._set_bg_normal()
                    self.next_label.config(text=self._next_label_line1)
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

        self._update_remaining_text()

    def _update_remaining_text(self) -> None:
        """キャッシュをもとに残り時間のみ更新"""
        if not self._next_alarm_cache:
            self.next_label.config(text="⏰ 次のアラーム：なし")
            return

        next_time_calc: datetime | None
        alarm: AlarmUI | None

        next_time_calc, alarm = self._next_alarm_cache

        if alarm and alarm.id and self.controller.is_alarm_triggered(alarm.id):
            self.next_label.config(text=f"{self._next_label_line1}\n鳴動中")
            return

        # 過去になっていたら再計算
        if next_time_calc is None or next_time_calc < datetime.now():
            self.next_label.config(text=self._next_label_line1)
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

        self.next_label.config(text=f"{self._next_label_line1}\n{remaining}")

    def _countdown_loop(self) -> None:
        self._update_remaining_text()
        self.root.after(1000, self._countdown_loop)

    # ---------------------------------------------------------
    # 🔧 Treeview セル内に Entry / Combobox を配置する共通関数
    # ---------------------------------------------------------
    def create_cell_editor(self, tree: ttk.Treeview, item_id: str, column_id: str, commit_callback: Callable[[str], None]) -> Callable[[tk.Entry | ttk.Combobox], None]:
        """
        Entry / Combobox などのウィジェットを Treeview のセル上に重ねて表示し、
        編集完了後 commit_callback(value) を呼び出す。
        """
        bbox = tree.bbox(item_id, column_id)
        if not bbox:
            return lambda widget: None  # type: ignore  # セルが不可視の場合
        x, y, width, height = bbox

        def editor_setter(widget: tk.Entry | ttk.Combobox) -> None:
            # 位置とサイズをセルに合わせる
            widget.place(in_=tree, x=x, y=y, width=width, height=height)

            # フォーカスを当てる
            widget.focus_set()

            # 編集完了（Enter）
            def done(event: tk.Event[tk.Widget] | None = None) -> None:
                value: str = widget.get()
                widget.destroy()
                commit_callback(value)

            # キャンセル（Escape）
            def cancel(event: tk.Event[tk.Widget] | None = None) -> None:
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
                manager_alarm_count=len(self.controller.get_all_alarm_uis()),
            )
            return

        self._refreshing_tree = True
        try:
            # ✅ TreeView が存在しない場合は終了
            if not hasattr(self, "tree") or not self.tree.winfo_exists():
                return

            self.tree.delete(*self.tree.get_children())

            for alarm in self.controller.get_all_alarm_uis():
                # ID 0（ダミー行など）は一覧に出さない
                try:
                    if not alarm.id:
                        continue
                except ValueError:
                    self._log_ui_warning(
                        "Skipped alarm with invalid id during refresh_tree",
                        alarm_data=alarm,
                        alarm_type=type(alarm).__name__,
                    )
                    continue
                dt: datetime | None = alarm.datetime_
                date_str: str = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else ""
                time_str: str = dt.strftime("%H:%M") if isinstance(dt, datetime) else ""

                # 曜日
                weekday_list: list[int] = list(alarm.weekday or [])
                weekday_str: str = weekday_to_str(weekday_list) if weekday_list else ""

                # 有効/祝日/スヌーズ
                enabled_str: str = "ON" if alarm.enabled else "OFF"
                skip_str: str = "✔" if alarm.skip_holiday else "×"
                snooze_limit: int = alarm.snooze_limit

                # 🔹 繰り返し表示（内部 → 日本語）
                repeat_type: str = alarm.repeat or "none"
                repeat_display: str = REPEAT_DISPLAY.get(repeat_type, repeat_type)

                # 🔹 カスタム詳細の日本語説明を生成
                custom_desc: str = ""
                if repeat_type == "custom":
                    weeks: list[int] = list(alarm.week_of_month or [])
                    interval: int = alarm.interval_weeks or 1
                    parts: list[str] = []

                    # 第n週
                    if weeks:
                        nth_text: str = "・".join([f"第{i}週" for i in weeks])
                        parts.append(nth_text)

                    # 曜日
                    if weekday_list:
                        parts.append("".join(WEEKDAY_LABELS[i] for i in weekday_list))

                    # 週おき
                    if interval > 1:
                        parts.append(f"{interval}週おき")

                    custom_desc: str = "／".join(parts) if parts else ""

                # 🔹 表示行を構築
                values: list[str | int] = [
                    alarm.id,
                    alarm.name,
                    date_str,
                    time_str,
                    repeat_display,
                    weekday_str,
                    enabled_str,
                    skip_str,
                    snooze_limit,
                    custom_desc,  # ← 新カラム
                ]
                self.tree.insert("", "end", values=values)

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
            self.main_frame, font=("Meiryo", 14), bg="#f0f0f0"  # ← 14 に変更
        )
        self.next_label.pack(pady=(0, 20))

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

        # --- スヌーズ入力 ---
        input_frame = tk.Frame(self.main_frame, bg="#f0f0f0")
        input_frame.pack(pady=(10, 0))

        tk.Label(input_frame, text="スヌーズ(分):", bg="#f0f0f0").pack(
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

    def _set_bg_normal(self) -> None:
        bg = "#f0f0f0"  # 通常時ライトグレー

        self.main_frame.config(bg=bg)
        self.date_label.config(bg=bg)
        self.time_label.config(bg=bg)
        self.next_label.config(bg=bg)

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
            ch: int = child.winfo_height()

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
        except Exception as e:
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
        except Exception as e:
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
        win.geometry("1080x830")
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
        self.repeat_combo.bind("<<ComboboxSelected>>", self.on_repeat_change)

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

        ttk.Label(form, text="スヌーズ上限：").grid(
            row=2, column=3, sticky="e", padx=padx, pady=pady
        )
        self.snooze_limit_combo = ttk.Combobox(
            form, values=[str(x) for x in range(1, 7)], width=6, state="readonly"
        )
        self.snooze_limit_combo.current(2)
        self.snooze_limit_combo.grid(row=2, column=4, sticky="w", padx=padx, pady=pady)

        # 音ファイル
        ttk.Label(form, text="音ファイル：").grid(
            row=3, column=3, sticky="e", padx=padx, pady=pady
        )
        self.sound_entry = ttk.Entry(form)
        self.sound_entry.grid(row=3, column=4, sticky="we", padx=padx, pady=pady)
        ttk.Button(
            form,
            text="選択",
            command=lambda: self.sound_entry.insert(0, filedialog.askopenfilename()),
        ).grid(row=3, column=5, padx=padx, pady=pady)

        # 登録ボタン
        ttk.Button(
            form, text="アラームを登録", width=20, command=self.add_alarm_action
        ).grid(row=4, column=0, columnspan=6, pady=(14, 5))

        # 画面部品をすべて作り終えてから一覧とラベルを更新する
        self.refresh_tree()
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
            self.place_window_near_parent(self.root, win, offset_x=40, offset_y=40)

        # --------------------------------------
        # ⑤ 閉じる処理
        # --------------------------------------
        win.protocol(
            "WM_DELETE_WINDOW", lambda: self.on_close(win, WINDOW_KEYS["SETTINGS"])
        )


    # ------------------
    # --- 登録済みアラーム削除ボタン ---
    # ------------------
    def delete_selected_alarms(self) -> None:
        """選択されたアラームをまとめて削除する"""
        tree: ttk.Treeview = self.tree
        if tree is None:
            return

        selected_items: tuple[str, ...] = tree.selection()

        if not selected_items:
            self._warn("警告", "削除する行を選択してください")
            return

        alarm_ids: list[str] = [str(tree.set(item, "id")) for item in selected_items]

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
        date: str | None = validate_date(date_raw)
        if date is None and date_raw != "":
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
            result: dict[str, Any] | None = self.custom_data
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

        # 😴 スヌーズ上限
        try:
            snooze_limit: int = int(self.snooze_limit_combo.get())
        except Exception:
            snooze_limit = 3

        ui_alarm = AlarmUI(
            id=None,
            name=name,
            date=date or "",
            time=time_str,
            repeat=repeat,
            weekday=weekday,
            week_of_month=week_of_month,
            interval_weeks=interval_weeks,
            enabled=True,
            sound=sound,
            skip_holiday=skip_holiday,
            snooze_minutes=self.controller.get_snooze_default_minutes(),
            snooze_limit=snooze_limit,
        )

        # ✅ Controller 経由で Manager へ登録
        self.controller.add_alarm_from_ui(ui_alarm)

        # 🌟 表示更新・通知
        self.refresh_tree()
        self.update_next_alarm_label()
        self._info("登録完了", f"「{name}」を登録しました。")

    # =========サブウインドウ・ダイアログ群=========
    # --------------------------------------------
    # 🔧 小ウインド位置ユーティリティ（全ウインド共通)
    # --------------------------------------------
    def place_subwindow_near_parent(
        self,
        parent: Any | tk.Tk,
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
            parent: Any | tk.Tk = getattr(self, "settings_window", self.root)
            self.place_subwindow_near_parent(parent, child)
            child.transient(parent)
            child.lift()
            child.focus_force()
        except Exception:
            pass

    # --------------------------------------------
    # 🔹 曜日選択ダイアログ（毎週専用）
    # --------------------------------------------
    def select_weekdays_dialog(self, initial=None) -> list[int] | None:
        """毎週繰り返し用のシンプルな曜日選択ダイアログ"""
        selected_days: list[int] = initial or []
        win = tk.Toplevel(self.root)
        # 位置復元（無ければドッキング）
        if not self.load_window_position(win, WINDOW_KEYS["WEEKDAY"]):
            self._dock_child_window(win)
        win.title("曜日の選択")
        win.geometry("420x180")
        win.resizable(False, False)

        win.protocol(
            "WM_DELETE_WINDOW", lambda: self.on_close(win, WINDOW_KEYS["WEEKDAY"])
        )

        ttk.Label(win, text="曜日を選択してください", font=("Meiryo", 12, "bold")).pack(
            pady=8
        )

        # 🔹 横並びレイアウト
        frame = ttk.Frame(win)
        frame.pack(padx=10, pady=5)

        weekday_vars: list[tk.BooleanVar] = []
        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.BooleanVar(value=i in selected_days)
            weekday_vars.append(var)
            ttk.Checkbutton(frame, text=label, variable=var).grid(
                row=0, column=i, padx=6, pady=4
            )

        # 🔹 ボタンフレーム
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=12)

        result: list[int] | None = None

        def on_ok() -> None:
            nonlocal result
            result: list[int] = [i for i, var in enumerate(weekday_vars) if var.get()]
            win.destroy()

        def on_clear() -> None:
            for v in weekday_vars:
                v.set(False)

        def on_cancel() -> None:
            nonlocal result
            result = None
            win.destroy()

        ttk.Button(btn_frame, text="OK", width=10, command=on_ok).grid(
            row=0, column=0, padx=10
        )
        ttk.Button(btn_frame, text="クリア", width=10, command=on_clear).grid(
            row=0, column=1, padx=10
        )
        ttk.Button(btn_frame, text="キャンセル", width=10, command=on_cancel).grid(
            row=0, column=2, padx=10
        )

        win.grab_set()
        # ---------------------------------------
        # ✅ 終了待機
        # ---------------------------------------
        win.wait_window()
        return result

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

    def open_custom_dialog(self, initial=None) -> dict[str, list[str] | int] | None:
        """第n週／曜日／週おきを設定できるカスタム設定ダイアログ"""
        initial = initial or {"weekday": [], "week_of_month": [], "interval_weeks": 1}

        win = tk.Toplevel(self.root)
        win.title("カスタム繰り返し設定")
        win.geometry("420x360")
        win.resizable(False, False)
        if not self.load_window_position(win, WINDOW_KEYS["CUSTOM"]):
            self._dock_child_window(win)
        try:
            parent: Any | tk.Tk = getattr(self, "settings_window", self.root)
            self.place_subwindow_near_parent(parent, win)
            win.transient(parent)
            win.lift()
            win.focus_force()
        except Exception:
            pass

        # === タイトル ===
        ttk.Label(win, text="🗓 カスタム繰り返し設定", font=("Meiryo", 12, "bold")).pack(
            pady=(10, 6)
        )

        # === 第n週 ===
        ttk.Label(
            win, text="■ 第n週の指定（複数可）", font=("Meiryo", 10, "bold")
        ).pack(pady=(6, 2))
        week_frame = ttk.Frame(win)
        week_frame.pack(pady=(0, 8))
        week_vars = []
        for i in range(1, 6):
            var = tk.BooleanVar(value=(i in initial.get("week_of_month", [])))
            ttk.Checkbutton(week_frame, text=f"第{i}週", variable=var).pack(
                side="left", padx=6
            )
            week_vars.append(var)

        # === 曜日 ===
        ttk.Label(win, text="■ 曜日の指定（複数可）", font=("Meiryo", 10, "bold")).pack(
            pady=(6, 2)
        )
        weekday_frame = ttk.Frame(win)
        weekday_frame.pack(pady=(0, 8))
        weekday_vars: list[tk.BooleanVar] = []
        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.BooleanVar(value=(i in initial.get("weekday", [])))
            ttk.Checkbutton(weekday_frame, text=label, variable=var).pack(
                side="left", padx=6
            )
            weekday_vars.append(var)

        # === 週おき ===
        ttk.Label(
            win, text="■ 繰り返し間隔（週おき）", font=("Meiryo", 10, "bold")
        ).pack(pady=(8, 3))
        interval_var = tk.StringVar(value=str(initial.get("interval_weeks", 1)))
        interval_combo = ttk.Combobox(
            win,
            textvariable=interval_var,
            values=["1", "2", "3", "4"],
            width=6,
            state="readonly",
        )
        interval_combo.pack(pady=(0, 12))

        # === ボタン列 ===
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=(10, 8))

        result: dict[str, list[str] | int] = {}

        def on_ok() -> None:
            result["week_of_month"] = [
                i + 1 for i, var in enumerate(week_vars) if var.get()
            ]
            result["weekday"] = [i for i, var in enumerate(weekday_vars) if var.get()]
            result["interval_weeks"] = int(interval_var.get())
            win.destroy()

        def on_clear() -> None:
            for var in week_vars + weekday_vars:
                var.set(False)
            interval_var.set("1")

        def on_cancel() -> None:
            result.clear()
            win.destroy()

        ttk.Button(btn_frame, text="OK", width=10, command=on_ok).pack(
            side="left", padx=8
        )
        ttk.Button(btn_frame, text="クリア", width=10, command=on_clear).pack(
            side="left", padx=8
        )
        ttk.Button(btn_frame, text="キャンセル", width=10, command=on_cancel).pack(
            side="left", padx=8
        )

        win.grab_set()
        win.wait_window()

        return result if result else None

    # --------------------------------------------
    # 🔹 新規登録フォーム用：曜日選択ハンドラ
    # --------------------------------------------
    def pick_weekday(self) -> None:
        """新規登録フォームの「曜日：選択」ボタンから呼ばれる"""
        result = self.select_weekdays_dialog(self.weekday_selected)
        if result is not None:
            self.weekday_selected = result
            # （お好みでボタンの表示を変えてもOK）
            # 表示例: "月水金" など
            label: LiteralString | Literal['選択'] = "".join(WEEKDAY_LABELS[i] for i in result) or "選択"
            self.weekday_btn.config(text=label)
            # weekly 系を選択中ならカスタム保持も同期しておく
            if self.repeat_combo.get().startswith("毎"):
                self.custom_data = {
                    "weekday": self.weekday_selected[:],
                    "week_of_month": [],
                    "interval_weeks": WEEKS_CUSTOM_INTERNAL.get(
                        self.repeat_combo.get(), 1
                    ),
                }

    def on_repeat_change(self, event: tk.Event | None = None) -> None:
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

    def open_custom_from_form(self):
        """詳細設定ボタンからカスタムダイアログを開く"""
        initial = self.custom_data or {
            "weekday": self.weekday_selected[:],
            "week_of_month": [],
            "interval_weeks": 1,
        }
        result: dict[str, list[str] | int] | None = self.open_custom_dialog(initial=initial)
        if result:
            self.custom_data = result
            # ボタンに簡易表示
            label: LiteralString | Literal['詳細設定'] = (
                "".join(WEEKDAY_LABELS[i] for i in result.get("weekday", []))
                or "詳細設定"
            )
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

        region: Literal['heading'] | Literal['separator'] | Literal['tree'] | Literal['cell'] | Literal['nothing'] = tree.identify_region(event.x, event.y)
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

        item: ttk._TreeviewItemDict = tree.item(item_id)
        values: list[Any] | Literal[''] = item.get("values")
        if not values:
            return "break"

        try:
            alarm_id = str(values[0])
        except Exception:
            return "break"

        alarm = self.controller.get_alarm_ui_by_id(alarm_id)
        if alarm is None:
            return "break"

        col_index = int(column_id[1:]) - 1
        columns = tree["columns"]
        if not (0 <= col_index < len(columns)):
            return "break"

        col_name = columns[col_index]
        old_value = values[col_index]

        def set_editor(widget, commit_callback) -> None:
            editor_setter: Callable[[Entry | Combobox], None] = self.create_cell_editor(
                tree, item_id, column_id, commit_callback
            )
            editor_setter(widget)

        if col_name == "weekday":
            current: list[int | str] = list(alarm.weekday or [])
            result: list[int | str] | None = self.select_weekdays_dialog(current)
            if result is None:
                return "break"
            self.controller.update_alarm_from_ui(
                alarm_id,
                AlarmUIPatch(weekday=result),
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

            def commit_repeat(value) -> None:
                internal = REPEAT_INTERNAL.get(value, "none")
                patch = AlarmUIPatch(
                    repeat=internal,
                    weekday=[],
                    week_of_month=[],
                    interval_weeks=1,
                )

                if internal.startswith("weekly_"):
                    interval_weeks = int(internal.split("_")[1])
                    result: list[str] | None = self.select_weekdays_dialog(list(alarm.weekday or []))
                    patch.interval_weeks = interval_weeks
                    patch.weekday = result if result else []
                elif internal == "custom":
                    result: dict[str, list[str] | int] | None = self.open_custom_dialog(
                        initial={
                            "weekday": list(alarm.weekday or []),
                            "week_of_month": list(alarm.week_of_month or []),
                            "interval_weeks": alarm.interval_weeks or 1,
                        }
                    )
                    if result:
                        patch.weekday = result["weekday"]
                        patch.week_of_month = result["week_of_month"]
                        patch.interval_weeks = result["interval_weeks"]

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

            def commit_enabled(value) -> None:
                self.controller.update_alarm_from_ui(
                    alarm_id,
                    AlarmUIPatch(enabled=(value == "ON")),
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

            def commit_skip(value) -> None:
                self.controller.update_alarm_from_ui(
                    alarm_id,
                    AlarmUIPatch(skip_holiday=(value == "✔")),
                )
                self.refresh_tree()
                self.update_next_alarm_label()

            set_editor(cb, commit_skip)
            cb.bind("<<ComboboxSelected>>", lambda e: commit_skip(cb.get()))
            cb.after(100, lambda: cb.event_generate("<Down>"))
            return "break"

        if col_name == "snooze_limit":
            cb = ttk.Combobox(tree, values=[1, 2, 3, 4, 5, 6], state="readonly")
            cb.set(str(alarm.snooze_limit))

            def commit_snooze(value) -> None:
                try:
                    snooze_limit = int(value)
                except Exception:
                    snooze_limit = 3
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

        if col_name == "date":
            if not alarm.date or not alarm.time:
                return "break"

            old_date: str = alarm.date
            new_date: date | None = self.select_date_dialog(old_date)
            if not new_date:
                return "break"

            self.controller.update_alarm_from_ui(
                alarm_id,
                AlarmUIPatch(date=new_date),
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

        if col_name == "name":
            entry = ttk.Entry(tree)
            entry.insert(0, old_value)

            def commit_text(value) -> None:
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
    def select_date_dialog(self, initial_date=None) -> date | None:
        """ミニカレンダーを開き、YYYY-MM-DD を返す"""
        from alarm.mini_calendar import MiniCalendar

        cal = MiniCalendar(
            self.root, initial_date=initial_date
        )
        return cal.show()

    # -----------------------------
    # 🕒 TimePicker 呼び出し関数(一覧編集用)
    # -----------------------------
    def select_time_dialog(self, initial_time=None) -> str | None:
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
        old: str | None = self.date_entry.get() or None
        new: str | None = self.select_date_dialog(old)
        if new:
            self.date_entry.config(state="normal")
            self.date_entry.delete(0, tk.END)
            self.date_entry.insert(0, new)
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
            snooze_min = int(self.snooze_entry.get())
            if snooze_min <= 0:
                raise ValueError
        except ValueError:
            snooze_min = self.controller.get_snooze_default_minutes()

        ok, alarm_name, next_time = self.controller.snooze_alarm_from_ui(snooze_min)
        if not ok:
            self._info("情報", "現在鳴動中のアラームはありません。")
            return

        self.player.stop()
        self.update_next_alarm_label()

        # 🌙 案内
        self._info(
            "スヌーズ設定",
            f"{alarm_name} を {snooze_min} 分後に再鳴動します。\n（{next_time.strftime('%H:%M') if next_time else '--:--'}）",
        )

    # --------------------------------------------
    # 🔹 起動
    # --------------------------------------------
    def start(self):
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
