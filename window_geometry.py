# -*- coding: utf-8 -*-
"""ウインドウジオメトリ情報モジュール
・window_geometry.py
・WindowGeometry（構造）
・from_dict / to_dict メソッド付きの dataclass
"""
#########################
# Author: F.Kurokawa
# Description:
# 　ウインドウジオメトリ情報モジュール(チェック済み)
#########################

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass
class WindowGeometry:
    """ウインドウジオメトリ情報"""
    x: int
    y: int
    width: int
    height: int

    @staticmethod
    def from_dict(d: Mapping[str, int]) -> "WindowGeometry":
        """辞書からウインドウジオメトリインスタンスを作成"""
        return WindowGeometry(
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
        )

    def to_dict(self) -> dict[str, int]:
        """ウインドウジオメトリを辞書に変換"""
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}
