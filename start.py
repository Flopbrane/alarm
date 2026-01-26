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

# 標準ライブラリ
import tkinter as tk
from tkinter import ttk

# 自作モジュール
from alarm_config_manager import Config, ConfigManager
from alarm_manager_temp import AlarmManager
from cui_controller import CUIController
from gui_controller import GUIController

# =====================================================
# 🔹 グローバル初期化（1回だけ）
# =====================================================
manager = AlarmManager()
cfg_mgr = ConfigManager()
cfg: Config = cfg_mgr.load_config()


# =====================================================
# 🔹 起動処理本体
# =====================================================
def start_application() -> None:
    """
    アプリ起動エントリーポイント
    """
    try:
        if cfg.show_dialog:
            show_mode_dialog()
        else:
            start_by_last_mode()

    except (FileNotFoundError, ValueError, KeyError) as e:
        # 🔴 最終セーフティネット
        print("[警告] 起動設定の読み込みに失敗しました")
        print(e)

        # 強制的にダイアログ起動
        show_mode_dialog()


def start_by_last_mode() -> None:
    """
    設定に従って GUI / CUI を直接起動
    """
    try:
        if cfg.last_mode == "gui":
            launch_gui()
        elif cfg.last_mode == "cui":
            launch_cui()
        else:
            show_mode_dialog()

    except (FileNotFoundError, ValueError, KeyError, AttributeError) as e:
        print("[警告] 最終モード起動に失敗しました")
        print(e)
        show_mode_dialog()


def launch_gui() -> None:
    """GUI 起動"""
    GUIController(manager).start()


def launch_cui() -> None:
    """CUI 起動"""
    CUIController(manager).run()


# =====================================================
# 🔹 起動モード選択ダイアログ
# =====================================================
def show_mode_dialog() -> None:
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
        text="GUI で起動",
        width=15,
        command=lambda: on_gui_selected(root),
    ).grid(row=0, column=0, padx=5)

    ttk.Button(
        btn_frame,
        text="CUI で起動",
        width=15,
        command=lambda: on_cui_selected(root),
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
def on_gui_selected(root: tk.Tk) -> None:
    """GUI 起動が選ばれた"""
    cfg.last_mode = "gui"
    cfg_mgr.save_config(cfg)

    root.destroy()  # ← Tk はここで完全終了
    launch_gui()


def on_cui_selected(root: tk.Tk) -> None:
    """CUI 起動が選ばれた"""
    cfg.last_mode = "cui"
    cfg_mgr.save_config(cfg)

    root.destroy()  # ← Tk はここで完全終了
    launch_cui()


# =====================================================
# 🔹 エントリーポイント
# =====================================================
if __name__ == "__main__":
    start_application()
