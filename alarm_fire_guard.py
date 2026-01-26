# -*- coding: utf-8 -*-
"""二重鳴動防止ガードモジュール
alarm + now + actual_now → True/False
(鳴らしていいか？鳴らさないか？の判定が役割)
"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_fire_guard.py
#########################
from datetime import datetime

from alarm_internal_model import AlarmStateInternal


# --------------------------------------------------------------
# 🔹 二重鳴動防止
# --------------------------------------------------------------
def check_last_fire(
    state: AlarmStateInternal,
    actual_now: datetime) -> bool:
    """ 直前発火チェック/5秒以内は無視
    👉 これは「repeat判定」ではありません
    👉 しかし「重要な実行安全性」の話です
    """
    # support being passed either an AlarmStateInternal or a full AlarmInternal
    last_fire: datetime | None = getattr(state, "last_fired_at", None)
    if last_fire and (actual_now - last_fire).total_seconds() < 5:
        return False
    return True
