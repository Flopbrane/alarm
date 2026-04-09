# -*- coding: utf-8 -*-
"""ログの種類定義"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from typing import NewType

ISODateTimeStr = NewType("ISODateTimeStr", str)
TraceId = NewType("TraceId", str)
LogLevelStr = NewType("LogLevelStr", str)
LogOutputStr = NewType("LogOutputStr", str)
