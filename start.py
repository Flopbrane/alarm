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
import threading
import tkinter as tk
import psutil
from tkinter import ttk
from typing import TYPE_CHECKING

# 自作モジュール
from logs.log_app import get_logger
from alarm_config_manager import Config, ConfigManager
from alarm_manager_temp import AlarmManager
from gui_starter import main as gui_main
from cui_starter import main as cui_main
if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger
# =====================================================
# 🔹 起動処理本体
# =====================================================
def start_application() -> None:
    """アプリケーションの起動処理"""
    try:
        logger: "AppLogger" = get_logger()
        boot_time: float = psutil.boot_time()

        logger.info(
            "アプリ起動",
            context={
                "boot_time": boot_time,
            }
        )

        manager = AlarmManager(
            logger=logger,
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
    from gui_controller import GUIController  # 循環インポート回避のため、ここでインポート
    GUIController(manager).start()


def launch_cui(manager: AlarmManager) -> None:
    from cui_controller import CUIController
    controller = CUIController(manager)
    t = threading.Thread(target=controller.run, daemon=False)
    t.start()


# =====================================================
# 🔹 起動モード選択ダイアログ
# =====================================================
def show_mode_dialog(
    manager: AlarmManager,
    cfg_mgr: ConfigManager,
    cfg: Config,
) -> None:
    """起動モード選択用の Tk ダイアログ"""
    print("ダイアログ表示前")
    root = tk.Tk()
    root.title("起動モードを選択")
    root.geometry("360x150")
    root.resizable(False, False)

    def handle_cui() -> None:
        on_cui_selected(root, manager, cfg_mgr, cfg)

    def handle_gui() -> None:
        on_gui_selected(root, manager, cfg_mgr, cfg)

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
        command=handle_gui,
    ).grid(row=0, column=0, padx=5)

    ttk.Button(
        btn_frame,
        text="ターミナルで起動",
        width=15,
        command=handle_cui,
    ).grid(row=0, column=1, padx=5)

    ttk.Button(
        btn_frame,
        text="キャンセル",
        width=15,
        command=root.destroy,
    ).grid(row=0, column=2, padx=5)
    # if command == root.destroy():
    #     print("キャンセルされました")

    print("mainloop入る")
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
    print("🔥 GUIボタン押された")
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
    print("🔥 CUIボタン押された")
    cfg.last_mode = "cui"
    cfg_mgr.save_config(cfg)

    root.destroy()  # ← Tk はここで完全終了
    launch_cui(manager)


# =====================================================
# 🔹 エントリーポイント
# =====================================================
if __name__ == "__main__":
    start_application()
