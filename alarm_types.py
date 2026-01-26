# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
#
#########################
# alarm_types.py
from __future__ import annotations
from datetime import date, time
from typing import TypeAlias
from pathlib import Path

DateType: TypeAlias = date | None
TimeType: TypeAlias = time | None
DateTimeType: TypeAlias = date | time | None
PathType: TypeAlias = str | Path
SoundType: TypeAlias = str | Path
UUIDType: TypeAlias = str
