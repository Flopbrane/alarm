# -*- coding: utf-8 -*-
# pylint: disable=C0301
"""カスタム繰り返し設定ダイアログ。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from alarm.constants import WEEKDAY_LABELS, WEEKS_DISPLAY
from alarm.window_keys import WindowKey


class CustomRepeatDialog:
    """カスタム繰り返し設定用の小ウインドウ。"""

    @staticmethod
    def _initial_int(value: list[int] | int | None, default: int) -> int:
        """初期値を安全に int 化する。"""
        if isinstance(value, int):
            return value
        return default

    def __init__(
        self,
        *,
        parent: tk.Misc,
        owner: tk.Misc,
        initial: dict[str, list[int] | int] | None,
        load_window_position: Callable[[tk.Misc, WindowKey], bool],
        save_window_position: Callable[[tk.Misc, WindowKey], None],
        dock_window: Callable[[tk.Toplevel], None],
    ) -> None:
        self.parent: tk.Misc = parent
        self.owner: tk.Misc = owner
        self.initial: dict[str, list[int] | int] = initial or {
            "weekday": [],
            "week_of_month": [],
            "interval_weeks": 1,
        }
        self._load_window_position: Callable[[tk.Misc, WindowKey], bool] = load_window_position
        self._save_window_position: Callable[[tk.Misc, WindowKey], None] = save_window_position
        self._dock_window: Callable[[tk.Toplevel], None] = dock_window
        self._result: dict[str, list[int] | int] | None = None

    def show(self) -> dict[str, list[int] | int] | None:
        """ダイアログを表示して結果を返す。"""
        win: tk.Toplevel = tk.Toplevel(self.owner)
        win.title("カスタム繰り返し設定")
        win.geometry("420x360")
        win.resizable(True, True)

        if not self._load_window_position(win, WindowKey.CUSTOM):
            self._dock_window(win)

        ttk.Label(
            win,
            text="カスタム繰り返し設定",
            font=("Meiryo", 12, "bold"),
        ).pack(pady=(10, 6))

        mode_var: tk.StringVar = tk.StringVar(value="week_of_month")
        mode_frame = ttk.Frame(win)
        mode_frame.pack(pady=(0, 8))
        ttk.Label(
            mode_frame,
            text="設定方法",
            font=("Meiryo", 10, "bold"),
        ).pack(side="left", padx=(0, 8))
        ttk.Radiobutton(
            mode_frame,
            text="第n週",
            variable=mode_var,
            value="week_of_month",
        ).pack(side="left", padx=4)
        ttk.Radiobutton(
            mode_frame,
            text="n週おき",
            variable=mode_var,
            value="interval_weeks",
        ).pack(side="left", padx=4)

        week_section = ttk.Frame(win)
        week_section.pack(fill="x", pady=(6, 8))
        ttk.Label(
            week_section,
            text="■ 第n週の指定（複数可、6=最終週）",
            font=("Meiryo", 10, "bold"),
        ).pack(pady=(0, 2))
        week_frame = ttk.Frame(week_section)
        week_frame.pack(pady=(0, 0))
        week_vars: list[tk.BooleanVar] = []
        week_checks: list[ttk.Checkbutton] = []
        week_of_month_value: list[int] | int = self.initial.get("week_of_month", [])
        week_of_month: list[int] = (
            week_of_month_value if isinstance(week_of_month_value, list) else []
        )
        for i in range(1, 7):
            var = tk.BooleanVar(value=i in week_of_month)
            label: str = "最終週" if i == 6 else f"第{i}週"
            check = ttk.Checkbutton(week_frame, text=label, variable=var)
            check.pack(side="left", padx=6)
            week_checks.append(check)
            week_vars.append(var)

        weekday_section = ttk.Frame(win)
        weekday_section.pack(fill="x", pady=(6, 8))
        ttk.Label(
            weekday_section,
            text="■ 曜日の指定（複数可）",
            font=("Meiryo", 10, "bold"),
        ).pack(pady=(0, 2))
        weekday_frame = ttk.Frame(weekday_section)
        weekday_frame.pack(pady=(0, 0))
        weekday_vars: list[tk.BooleanVar] = []
        weekday_value: list[int] | int = self.initial.get("weekday", [])
        weekday: list[int] = weekday_value if isinstance(weekday_value, list) else []
        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.BooleanVar(value=i in weekday)
            ttk.Checkbutton(weekday_frame, text=label, variable=var).pack(
                side="left", padx=6
            )
            weekday_vars.append(var)

        interval_section = ttk.Frame(win)
        interval_section.pack(fill="x", pady=(8, 8))
        ttk.Label(
            interval_section,
            text="■ 繰り返し間隔（週おき）",
            font=("Meiryo", 10, "bold"),
        ).pack(pady=(0, 3))
        interval_value: int = self._initial_int(self.initial.get("interval_weeks", 1), 1)
        interval_display_map: dict[str, int] = {
            label: value for value, label in WEEKS_DISPLAY.items()
        }
        interval_reverse_map: dict[int, str] = {
            value: label for label, value in interval_display_map.items()
        }
        interval_var: tk.StringVar = tk.StringVar(
            value=interval_reverse_map.get(interval_value, "毎週")
        )
        interval_combo = ttk.Combobox(
            interval_section,
            textvariable=interval_var,
            values=list(interval_display_map.keys()),
            width=16,
            state="readonly",
        )
        interval_combo.pack(pady=(0, 0))

        def _set_mode_state() -> None:
            """選択モードに応じて、逆側の入力欄を無効化する。"""
            if mode_var.get() == "week_of_month":
                for check in week_checks:
                    check.state(["!disabled"])
                interval_combo.state(["disabled"])
            else:
                for check in week_checks:
                    check.state(["disabled"])
                interval_combo.state(["!readonly"])
                interval_combo.state(["!disabled", "readonly"])

        def on_mode_change() -> None:
            _set_mode_state()

        def _on_mode_change(*_args: object) -> None:
            on_mode_change()

        mode_var.trace_add("write", _on_mode_change)

        if interval_value > 1:
            mode_var.set("interval_weeks")
        elif week_of_month:
            mode_var.set("week_of_month")
        _set_mode_state()

        def on_ok() -> None:
            selected_mode: str = mode_var.get()
            self._result = {
                "week_of_month": [
                    i + 1 for i, var in enumerate(week_vars) if var.get()
                ] if selected_mode == "week_of_month" else [],
                "weekday": [i for i, var in enumerate(weekday_vars) if var.get()],
                "interval_weeks": (
                    interval_display_map.get(interval_var.get(), 1)
                    if selected_mode == "interval_weeks"
                    else 1
                ),
            }
            self._save_window_position(win, WindowKey.CUSTOM)
            win.destroy()

        def on_clear() -> None:
            for var in week_vars + weekday_vars:
                var.set(False)
            interval_var.set("1")
            mode_var.set("week_of_month")
            _set_mode_state()

        def on_cancel() -> None:
            self._result = None
            self._save_window_position(win, WindowKey.CUSTOM)
            win.destroy()

        def on_close() -> None:
            on_cancel()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=(10, 8))
        ttk.Button(btn_frame, text="OK", width=10, command=on_ok).pack(
            side="left", padx=8
        )
        ttk.Button(btn_frame, text="クリア", width=10, command=on_clear).pack(
            side="left", padx=8
        )
        ttk.Button(btn_frame, text="キャンセル", width=10, command=on_cancel).pack(
            side="left", padx=8
        )

        win.protocol("WM_DELETE_WINDOW", on_close)
        win.grab_set()
        win.wait_window()
        return self._result
