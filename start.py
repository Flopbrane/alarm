#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GUI/CUI 起動選択ダイアログ"""
#########################
# Author: F.Kurokawa
# Description:
# GUI/CUI 起動選択ダイアログ
#########################

# 標準ライブラリ
import tkinter as tk
from tkinter import ttk

# 自作モジュール
from alarm_config_manager import Config, ConfigManager
from cui import main
from gui import AlarmGUI

cfg_mgr = ConfigManager()

def start_gui_mode(root: tk.Tk | None = None) -> None:
    """GUIモードで起動"""
    cfg: Config
    cfg = cfg_mgr.load_config()
    cfg.last_mode = "gui"
    cfg_mgr.save_config(cfg)

    if root is not None:
        root.destroy()

    app = AlarmGUI()
    app.start_gui()


def start_cui_mode(root: tk.Tk | None = None) -> None:
    """CUIモードで起動"""
    cfg: Config
    cfg = cfg_mgr.load_config()
    cfg.last_mode = "cui"
    cfg_mgr.save_config(cfg)

    if root is not None:
        root.destroy()

    main()


def show_mode_dialog() -> None:
    """起動モード選択ダイアログを表示する"""
    root = tk.Tk()
    root.title("起動モードを選択")
    root.geometry("360x150")
    root.resizable(True, True)

    ttk.Label(root, text="起動モードを選んでください", font=("Meiryo", 12)).pack(
        pady=15
    )

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=5)

    ttk.Button(
        btn_frame, text="ウインドで起動", width=15, command=lambda: start_gui_mode(root)
    ).grid(row=0, column=0, padx=5)

    ttk.Button(
        btn_frame, text="ターミナルで起動", width=15, command=lambda: start_cui_mode(root)
    ).grid(row=0, column=1, padx=5)

    ttk.Button(btn_frame, text="キャンセル", width=15, command=root.destroy).grid(
        row=0, column=2, padx=5
    )

    root.mainloop()


def start() -> None:
    """メイン関数"""
    cfg: Config
    cfg = cfg_mgr.load_config()

    # show_startup_dialog = False の時 → 自動で last_mode に従って起動
    if not getattr(cfg, "show_startup_dialog", True):
        if getattr(cfg, "last_mode", "") == "":
            return start_cui_mode()
        else:
            return start_gui_mode()

    # 通常 → モード選択ダイアログ表示
    show_mode_dialog()


if __name__ == "__main__":
    start()
