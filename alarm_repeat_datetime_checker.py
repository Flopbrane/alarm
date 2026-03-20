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

from datetime import datetime, timedelta

from alarm_internal_model import AlarmInternal
from alarm_states_model import AlarmStateInternal
from logs.multi_info_logger import AppLogger
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

    FIRE_WINDOW_SECONDS = 2  # 発火許容ウィンドウ秒数
    MULTI_FIRE_GUARD_SECONDS = 5  # 多重発火ガード秒数

    def __init__(
        self,
        alarm: AlarmInternal,
        state: AlarmStateInternal,
        now: datetime,
        logger: AppLogger) -> None:
        """コンストラクタ"""
        self.alarm: AlarmInternal = alarm
        self.state: AlarmStateInternal = state
        self.drive_now: datetime = now
        self.logger: AppLogger = logger

    # --------------------------------------------------------------
    # 🔹 repeat 設定に応じて、本当に鳴らして良いのかの最終判断
    # --------------------------------------------------------------
    def should_fire(self) -> bool:
        """本当に鳴らして良いのかの最終判断"""

        now: datetime = self.drive_now  # Manager が供給する内部クロック

        # 🔒 単発アラームの最終ガード
        if self.alarm.repeat == "single" and self.state.last_fired_at is not None:
            return False

        # ❶ 異常状態は即拒否（ログ対象）
        if self.state.is_invalid_state:
            self.logger.error(
                message=f"invalid state: {self.state}",
                alarm_id=self.alarm.id,
                context={
                    "state_id": self.state.id,
                    "next_fire": self.state.next_fire_datetime,
                    "repeat": self.alarm.repeat,
                    "now": now,
                    "state_triggered": self.state.triggered,
                    "state_last_fired_at": self.state.last_fired_at,
                },
            )  # pylint: disable=fixme
            return False

        # ❷ 未計算・終了状態は鳴らさない
        if self.state.is_uncomputed or self.state.is_finished:
            return False

        # ❸ 多重発火ガード（短時間）
        if self.state.last_fired_at:
            if (now - self.state.last_fired_at).total_seconds() < self.MULTI_FIRE_GUARD_SECONDS:
                return False

        # ❹ 予定時刻に到達したか
        if self.state.next_fire_datetime is None:
            return False
        # ❺ 予定時刻が1分以上過去なら鳴らさない（遅延発火防止）
        if self.state.next_fire_datetime < self.drive_now - timedelta(minutes=1):
            return False
        # ❻ 予定時刻から2秒以内なら鳴らす
        fire_from: datetime = self.state.next_fire_datetime
        fire_until: datetime = fire_from + timedelta(seconds=self.FIRE_WINDOW_SECONDS)
        return fire_from <= self.drive_now <= fire_until


# =============================================================
