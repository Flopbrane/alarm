# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
#
#########################
# alarm/logger_bridge.py
from __future__ import annotations

from typing import TYPE_CHECKING

from logs.log_app import get_logger

if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger


def get_alarm_logger() -> "AppLogger":
    """alarm_project 用の Logger 取得口。"""
    return get_logger()
