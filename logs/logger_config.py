# -*- coding: utf-8 -*-
"""基準時間精度を設定する"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from dataclasses import dataclass


@dataclass
class LoggerConfig:
    """基準時間精度を設定する"""
    time_precision: str = "second"  # or "micro"
    timezone: str = "UTC"
    time_format: str = "%Y-%m-%d %H:%M:%S"
