# -*- coding: utf-8 -*-
"""曜日選択ダイアログ。"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from alarm.constants import WEEKDAY_LABELS
from alarm.window_keys import WindowKey


class WeekdaySelectDialog:
    """毎週/曜日選択用の小ウインドウ。"""

    def __init__(
        self,
        *,
        parent: tk.Misc,
        owner: tk.Misc,
        initial: list[int] | None = None,
        load_window_position: Callable[[tk.Misc, WindowKey], bool],
        save_window_position: Callable[[tk.Misc, WindowKey], None],
        dock_window: Callable[[tk.Toplevel], None],
    ) -> None:
        self.parent: tk.Misc = parent
        self.owner: tk.Misc = owner
        self.initial: list[int] = initial or []
        self._load_window_position: Callable[[tk.Misc, WindowKey], bool] = load_window_position
        self._save_window_position: Callable[[tk.Misc, WindowKey], None] = save_window_position
        self._dock_window: Callable[[tk.Toplevel], None] = dock_window
        self._result: list[int] | None = None

    def show(self) -> list[int] | None:
        """ダイアログを表示して選択結果を返す。"""
        win = tk.Toplevel(self.owner)
        win.title("曜日の選択")
        win.geometry("420x180")
        win.resizable(False, False)

        if not self._load_window_position(win, WindowKey.WEEKDAY):
            self._dock_window(win)

        ttk.Label(
            win,
            text="曜日を選択してください",
            font=("Meiryo", 12, "bold"),
        ).pack(pady=8)

        frame = ttk.Frame(win)
        frame.pack(padx=10, pady=5)

        weekday_vars: list[tk.BooleanVar] = []
        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.BooleanVar(value=i in self.initial)
            weekday_vars.append(var)
            ttk.Checkbutton(frame, text=label, variable=var).grid(
                row=0, column=i, padx=6, pady=4
            )

        def on_ok() -> None:
            """OKボタンが押されたときの処理"""
            self._result = [i for i, var in enumerate(weekday_vars) if var.get()]
            self._save_window_position(win, WindowKey.WEEKDAY)
            win.destroy()

        def on_clear() -> None:
            """クリアボタンが押されたときの処理"""
            for var in weekday_vars:
                var.set(False)

        def on_cancel() -> None:
            """キャンセルボタンが押されたときの処理"""
            self._result = None
            self._save_window_position(win, WindowKey.WEEKDAY)
            win.destroy()

        def on_close() -> None:
            """ウィンドウが閉じられたときの処理"""
            on_cancel()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=12)

        ttk.Button(btn_frame, text="OK", width=10, command=on_ok).grid(
            row=0, column=0, padx=10
        )
        ttk.Button(btn_frame, text="クリア", width=10, command=on_clear).grid(
            row=0, column=1, padx=10
        )
        ttk.Button(btn_frame, text="キャンセル", width=10, command=on_cancel).grid(
            row=0, column=2, padx=10
        )

        win.protocol("WM_DELETE_WINDOW", on_close)
        win.grab_set()
        win.wait_window()
        return self._result
