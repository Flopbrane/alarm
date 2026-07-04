# -*- coding: utf-8 -*-
"""日付ルール判定用ユーティリティ"""
#########################
# Author: F.Kurokawa
# Description:
# 日付ルール判定用ユーティリティ(チェック済み)
#########################

import datetime
import calendar
from typing import Sequence


# ===============================
# 🔹 日付ルール判定用ユーティリティ
# ===============================
def is_valid_week_of_month(
    now: datetime.date | datetime.datetime,
    valid_weeks: Sequence[int] | None
    ) -> bool:
    """第 n 週に該当するか判定する（valid_weeks=[1,3] など）"""
    if not valid_weeks:
        return True

    week_num: int = (now.day - 1) // 7 + 1
    if week_num in valid_weeks:
        return True

    if 6 not in valid_weeks:
        return False

    last_day: int = calendar.monthrange(now.year, now.month)[1]
    return now.day >= max(1, last_day - 6)


def is_valid_interval_week(now_week: int, base_week: int, interval_weeks: int) -> bool:
    """週おき（interval_weeks）に該当するか判定"""
    diff: int = now_week - base_week
    return (diff % interval_weeks) == 0
