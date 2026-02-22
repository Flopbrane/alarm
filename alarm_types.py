# -*- coding: utf-8 -*-
"""アラームの時間型定義モジュール
"""
#########################
# Author: F.Kurokawa
# Description:
# アラームの時間型定義モジュール
#########################
# alarm_types.py
from __future__ import annotations
from datetime import date, time, datetime
from typing import TypeAlias
from pathlib import Path

DateType: TypeAlias = date | None
TimeType: TypeAlias = time | None
DateTimeType: TypeAlias = date | time | datetime | None

PathType: TypeAlias = str | Path
SoundType: TypeAlias = str | Path
UUIDType: TypeAlias = str | None
