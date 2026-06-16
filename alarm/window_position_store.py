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

import json
from typing import Dict

from env_paths import WINDOW_POSITION_PATH
from window_geometry import WindowGeometry
from window_keys import WindowKey


class WindowPositionStore:
    """🗂 ウインドウ位置の永続化専用"""

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
