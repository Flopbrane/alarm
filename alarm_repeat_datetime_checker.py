# -*- coding: utf-8 -*-
# pylint: disable=W0212
"""繰り返し値により、発火判定を行うモジュール
alarm + now + actual_now → True/False
(鳴らすか？鳴らさないか？の判定が役割)

今この瞬間に「鳴らしていいか」？=発火判定エンジン
→このアラームは、今、鳴っていい存在か？"""
#########################
# Author: F.Kurokawa
# Description:
# 繰り返し値により、発火判定を行うモジュール(チェック済み)
#########################

from datetime import datetime

from alarm_internal_model import AlarmStateInternal

# =============================================================

class AlarmDatetimeChecker:
    """繰り返しルール判定クラス
        state の状態	    should_fire()	意味
    is_uncomputed	            False	「まだ準備できてない」
    has_next_schedule & 未到達	False	「時刻が来てない」
    is_finished	                False	「寿命終了」
    is_invalid_state	        False	「異常、無視」
    has_next_schedule & 到達	True	「鳴らせ」
    """
    def __init__(self, state: AlarmStateInternal, now: datetime) -> None:
        self.state: AlarmStateInternal = state
        self.drive_now: datetime = now
    # --------------------------------------------------------------
    # 🔹 repeat 設定に応じて、本当に鳴らして良いのかの最終判断
    # --------------------------------------------------------------
    def should_fire(self) -> bool:
        """本当に鳴らして良いのかの最終判断"""
        now: datetime = self.drive_now  # Manager が供給する内部クロック

        # ❶ 異常状態は即拒否（ログ対象）
        if self.state.is_invalid_state:
            print(f"[エラー] 異常状態検出: next_fire_datetime={self.state.next_fire_datetime}, "
                  f"lifecycle_finished={self.state.lifecycle_finished}, id={self.state.id}")
            return False

        # ❷ 未計算・終了状態は鳴らさない
        if self.state.is_uncomputed or self.state.is_finished:
            return False

        # ❸ 多重発火ガード（短時間）
        if self.state.last_fired_at:
            if (now - self.state.last_fired_at).total_seconds() < 5:
                return False

        # ❹ 予定時刻に到達したか
        if self.state.next_fire_datetime is None:
            return False

        return now >= self.state.next_fire_datetime

# =============================================================
