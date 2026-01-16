# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
#
#########################
# 自作定数モジュール
from constants import WEEKDAY_LABELS
from typing import List

def weekday_to_str(weekday_list: List[int]) -> str:
    """例: [0,2,4] → '月水金'"""
    if not weekday_list:
        return ""
    return "".join(WEEKDAY_LABELS[i] for i in weekday_list)
