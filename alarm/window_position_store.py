# -*- coding: utf-8 -*-
"""移動されたウインドの位置を保存・復元するモジュール
window_position_manager.py
・Tkinter と会話する
・ウインドウのgeometry 文字列を読み・解析し、辞書に変換する
・最後は WindowGeometry に変換する
"""
#########################
# Author: F.Kurokawa
# Description:
# ウィンドウ位置管理モジュール(GUIウインドウ用)(チェック済み)
#########################
# window_position_store.py
from __future__ import annotations

import tkinter as tk
import json
from typing import Dict

from alarm.env_paths import WINDOW_POSITION_PATH
from alarm.window_geometry import WindowGeometry
from alarm.window_keys import WindowKey


class WindowPositionStore:
    """🗂 ウインドウ位置の永続化専用"""

    @staticmethod
    def load_window_position(window:tk.Misc, key: WindowKey) -> bool:
        """既存 GUI 互換: 単一ウインドウ位置を復元する。"""
        all_data: Dict[WindowKey, WindowGeometry] = WindowPositionStore.load_all()
        geometry: WindowGeometry | None = all_data.get(key)
        if geometry is None:
            return False

        window.geometry(
            f"{geometry.width}x{geometry.height}+{geometry.x}+{geometry.y}"
        )
        return True

    @staticmethod
    def save_window_position(window:tk.Misc, key: WindowKey) -> None:
        """既存 GUI 互換: 単一ウインドウ位置を保存する。"""
        window.update_idletasks()

        all_data: Dict[WindowKey, WindowGeometry] = WindowPositionStore.load_all()
        all_data[key] = WindowGeometry(
            x=int(window.winfo_x()),
            y=int(window.winfo_y()),
            width=int(window.winfo_width()),
            height=int(window.winfo_height()),
        )
        WindowPositionStore.save_all(all_data)

    @staticmethod
    def load_all() -> Dict[WindowKey, WindowGeometry]:
        """全ウインドウ位置の読み込み"""
        if not WINDOW_POSITION_PATH.exists():
            return {}

        with open(WINDOW_POSITION_PATH, "r", encoding="utf-8") as f:
            raw: dict[str, dict[str, int]] = json.load(f)

        result: Dict[WindowKey, WindowGeometry] = {}
        for key_str, geo_dict in raw.items():
            try:
                key = WindowKey(key_str)
                result[key] = WindowGeometry.from_dict(geo_dict)
            except (ValueError, KeyError, TypeError):
                # 壊れたエントリは無視
                continue
        return result

    @staticmethod
    def save_all(data: Dict[WindowKey, WindowGeometry]) -> None:
        """全ウインドウ位置の保存"""
        raw: Dict[str, Dict[str, int]] = {k.value: v.to_dict() for k, v in data.items()}
        with open(WINDOW_POSITION_PATH, "w", encoding="utf-8") as f:
            json.dump(raw, f, ensure_ascii=False, indent=2)
