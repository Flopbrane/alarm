# -*- coding: utf-8 -*-
"""曜日表示フォーマッタモジュール(GUI専用)
weekday_list (list[int]) → str 変換
"""
#########################
# Author: F.Kurokawa
# Description:
# 「表示専用ユーティリティ」に固定するのが正解
#########################
# 自作定数モジュール
from typing import List

from constants import WEEKDAY_LABELS


def weekday_to_str(weekday_list: List[int]) -> str:
    """例: [0,2,4] → '月水金'"""
    if not weekday_list:
        return ""
    return "".join(WEEKDAY_LABELS[i] for i in weekday_list)
