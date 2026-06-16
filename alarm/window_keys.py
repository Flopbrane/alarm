# -*- coding: utf-8 -*-
#########################
# Author: F.Kurokawa
# Description:
## window_keys.py（チェック済み）
#########################
"""ウインドウ位置保存用キー定義モジュール"""
# Enum は 不正値を受け取った時点で ValueError を投げるため、
# 安全にキー変換ができる。
from enum import Enum


class WindowKey(str, Enum):
    """ウインドウ位置保存用キー"""

    MAIN = "MAIN"
    SETTINGS = "SETTINGS"
    ALARM_EDIT = "ALARM_EDIT"
    CALENDAR = "CALENDAR"
    TIME = "TIME"
    WEEKDAY = "WEEKDAY"
    CUSTOM = "CUSTOM"
    LAUNCHER = "LAUNCHER"
    ABOUT = "ABOUT"
