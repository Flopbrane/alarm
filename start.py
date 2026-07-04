#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=C0301
"""Application entry point."""
from __future__ import annotations

import tkinter as tk

import psutil

from alarm.alarm_app import AlarmApp, create_alarm_app
from alarm.alarm_config_manager import Config, Mode
from alarm.app_lock import AppLock
from alarm.cui_starter import main as cui_main
from alarm.gui_starter import main as gui_main
from alarm.logger_bridge import AlarmLogger, get_alarm_logger


def start_application() -> None:
    """Start exactly one UI mode through the shared app wiring."""
    logger: AlarmLogger | None = None

    with AppLock():
        try:
            logger = get_alarm_logger()
            logger.info("アプリ起動", context={"boot_time": psutil.boot_time()})

            app: AlarmApp = create_alarm_app(logger)
            app.manager.start_cycle("startup")

            cfg: Config = app.config
            if cfg.show_dialog:
                mode: Mode | None = choose_mode_with_dialog(cfg.last_mode)
                if mode is None:
                    return
                app.config.last_mode = mode
                app.config_manager.save_config(app.config)
            else:
                mode = cfg.last_mode

            if mode == "gui":
                gui_main(app)
            else:
                cui_main(app)

        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"[エラー] アプリケーションの起動に失敗しました: {exc}")
            if logger is not None:
                logger.error(
                    "アプリケーションの起動に失敗しました",
                    context={"error": str(exc)},
                )


def choose_mode_with_dialog(default_mode: Mode) -> Mode | None:
    """Ask the user to choose one mode only."""
    root: tk.Tk = tk.Tk()
    root.title("起動モードを選択")
    root.geometry("450x150")
    root.resizable(True, True)

    result: dict[str, Mode | None] = {"mode": default_mode}

    def select(mode: Mode | None) -> None:
        result["mode"] = mode
        root.destroy()

    tk.Label(root, text="起動モードを選んでください", font=("Meiryo", 12)).pack(pady=15)
    frame: tk.Frame = tk.Frame(root)
    frame.pack(pady=5)
    tk.Button(frame, text="ウインドウで起動", width=15, command=lambda: select("gui")).grid(row=0, column=0, padx=5)
    tk.Button(frame, text="ターミナルで起動", width=15, command=lambda: select("cui")).grid(row=0, column=1, padx=5)
    tk.Button(frame, text="キャンセル", width=15, command=lambda: select(None)).grid(row=0, column=2, padx=5)

    root.mainloop()
    return result["mode"]


if __name__ == "__main__":
    start_application()
