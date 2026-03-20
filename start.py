#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI / CUI 起動選択エントリーポイント
Tk は「起動モード選択」にしか使わない
"""
#########################
# Author: F.Kurokawa
# Description:
# start.py
#########################
from __future__ import annotations

# 標準ライブラリ
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

# 自作モジュール
from log_app import get_logger
from alarm_config_manager import Config, ConfigManager
from alarm_manager_temp import AlarmManager
from cui_controller import CUIController
from gui_controller import GUIController
from logs.multi_info_logger import new_trace_id
if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger
# =====================================================
# 🔹 起動処理本体
# =====================================================
def start_application() -> None:
    """アプリケーションの起動処理"""
    try:
        logger: "AppLogger" = get_logger()
        trace_id: str = new_trace_id()

        logger.info(
            "アプリ起動",
            context={"trace_id": trace_id},
        )

        manager = AlarmManager(
            logger=logger,
            trace_id=trace_id,
        )

        cfg_mgr = ConfigManager()
        cfg: Config = cfg_mgr.load_config()

        if cfg.show_dialog:
            show_mode_dialog(manager, cfg_mgr, cfg)
        else:
            start_by_last_mode(manager, cfg_mgr, cfg)

    except Exception as e:  # pylint: disable=broad-exception-caught
        print("[警告] 起動失敗")
        print(e)


def start_by_last_mode(
    manager: AlarmManager,
    cfg_mgr: ConfigManager,
    cfg: Config
    ) -> None:
    """
    設定に従って GUI / CUI を直接起動
    """
    try:
        if cfg.last_mode == "gui":
            launch_gui(manager)
        elif cfg.last_mode == "cui":
            launch_cui(manager)
        else:
            show_mode_dialog(manager, cfg_mgr, cfg)

    except (FileNotFoundError, ValueError, KeyError, AttributeError) as e:  # pylint: disable=broad-exception-caught
        print("[警告] 最終モード起動に失敗しました")
        print(e)
        show_mode_dialog(manager, cfg_mgr, cfg)


def launch_gui(manager: AlarmManager) -> None:
    """GUI 起動"""
    GUIController(manager).start()


def launch_cui(manager: AlarmManager) -> None:
    """CUI 起動"""
    CUIController(manager).run()


# =====================================================
# 🔹 起動モード選択ダイアログ
# =====================================================
def show_mode_dialog(
    manager: AlarmManager,
    cfg_mgr: ConfigManager,
    cfg: Config,
) -> None:
    """起動モード選択用の Tk ダイアログ"""
    root = tk.Tk()
    root.title("起動モードを選択")
    root.geometry("360x150")
    root.resizable(False, False)

    ttk.Label(
        root,
        text="起動モードを選んでください",
        font=("Meiryo", 12),
    ).pack(pady=15)

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=5)

    ttk.Button(
        btn_frame,
        text="ウインドウで起動",
        width=15,
        command=lambda: on_gui_selected(root, manager, cfg_mgr, cfg),
    ).grid(row=0, column=0, padx=5)

    ttk.Button(
        btn_frame,
        text="ターミナルで起動",
        width=15,
        command=lambda: on_cui_selected(root, manager, cfg_mgr, cfg),
    ).grid(row=0, column=1, padx=5)

    ttk.Button(
        btn_frame,
        text="キャンセル",
        width=15,
        command=root.destroy,
    ).grid(row=0, column=2, padx=5)

    root.mainloop()


# =====================================================
# 🔹 ボタンイベント
# =====================================================
def on_gui_selected(
    root: tk.Tk,
    manager: AlarmManager,
    cfg_mgr: ConfigManager,
    cfg: Config) -> None:
    """GUI 起動が選ばれた"""
    cfg.last_mode = "gui"
    cfg_mgr.save_config(cfg)

    root.destroy()  # ← Tk はここで完全終了
    launch_gui(manager)


def on_cui_selected(
    root: tk.Tk,
    manager: AlarmManager,
    cfg_mgr: ConfigManager,
    cfg: Config) -> None:
    """CUI 起動が選ばれた"""
    cfg.last_mode = "cui"
    cfg_mgr.save_config(cfg)

    root.destroy()  # ← Tk はここで完全終了
    launch_cui(manager)


# =====================================================
# 🔹 エントリーポイント
# =====================================================
if __name__ == "__main__":
    start_application()
