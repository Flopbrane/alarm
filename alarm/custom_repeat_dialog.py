# -*- coding: utf-8 -*-
"""カスタム繰り返し設定ダイアログ。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from alarm.constants import WEEKDAY_LABELS
from alarm.window_keys import WindowKey


class CustomRepeatDialog:
    """カスタム繰り返し設定用の小ウインドウ。"""

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
        win = tk.Toplevel(self.owner)
        win.title("カスタム繰り返し設定")
        win.geometry("420x360")
        win.resizable(False, False)

        if not self._load_window_position(win, WindowKey.CUSTOM):
            self._dock_window(win)

        ttk.Label(
            win,
            text="カスタム繰り返し設定",
            font=("Meiryo", 12, "bold"),
        ).pack(pady=(10, 6))

        ttk.Label(
            win,
            text="■ 第n週の指定（複数可）",
            font=("Meiryo", 10, "bold"),
        ).pack(pady=(6, 2))
        week_frame = ttk.Frame(win)
        week_frame.pack(pady=(0, 8))
        week_vars: list[tk.BooleanVar] = []
        week_of_month_value: list[int] | int = self.initial.get("week_of_month", [])
        week_of_month: list[int] = (
            week_of_month_value if isinstance(week_of_month_value, list) else []
        )
        for i in range(1, 6):
            var = tk.BooleanVar(value=i in week_of_month)
            ttk.Checkbutton(week_frame, text=f"第{i}週", variable=var).pack(
                side="left", padx=6
            )
            week_vars.append(var)

        ttk.Label(
            win,
            text="■ 曜日の指定（複数可）",
            font=("Meiryo", 10, "bold"),
        ).pack(pady=(6, 2))
        weekday_frame = ttk.Frame(win)
        weekday_frame.pack(pady=(0, 8))
        weekday_vars: list[tk.BooleanVar] = []
        weekday_value: list[int] | int = self.initial.get("weekday", [])
        weekday: list[int] = weekday_value if isinstance(weekday_value, list) else []
        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.BooleanVar(value=i in weekday)
            ttk.Checkbutton(weekday_frame, text=label, variable=var).pack(
                side="left", padx=6
            )
            weekday_vars.append(var)

        ttk.Label(
            win,
            text="■ 繰り返し間隔（週おき）",
            font=("Meiryo", 10, "bold"),
        ).pack(pady=(8, 3))
        interval_var = tk.StringVar(
            value=str(self.initial.get("interval_weeks", 1))
        )
        interval_combo = ttk.Combobox(
            win,
            textvariable=interval_var,
            values=["1", "2", "3", "4"],
            width=6,
            state="readonly",
        )
        interval_combo.pack(pady=(0, 12))

        def on_ok() -> None:
            self._result = {
                "week_of_month": [
                    i + 1 for i, var in enumerate(week_vars) if var.get()
                ],
                "weekday": [i for i, var in enumerate(weekday_vars) if var.get()],
                "interval_weeks": int(interval_var.get()),
            }
            self._save_window_position(win, WindowKey.CUSTOM)
            win.destroy()

        def on_clear() -> None:
            for var in week_vars + weekday_vars:
                var.set(False)
            interval_var.set("1")

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
