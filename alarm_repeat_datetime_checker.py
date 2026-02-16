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

<<<<<<< HEAD
from datetime import datetime, timedelta

from alarm_internal_model import AlarmInternal, AlarmStateInternal
from alarm_irregular_logger import AlarmLogger, LogWhere
=======
from datetime import datetime

from alarm_internal_model import AlarmStateInternal

>>>>>>> d2d7f4750c98bc7b8db33fdf03ac1e740a9fdc27
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
<<<<<<< HEAD

    FIRE_WINDOW_SECONDS = 2  # 発火許容ウィンドウ秒数
    MULTI_FIRE_GUARD_SECONDS = 5  # 多重発火ガード秒数

    def __init__(
        self,
        alarm: AlarmInternal,
        state: AlarmStateInternal,
        now: datetime,
        logger: AlarmLogger) -> None:
        """コンストラクタ"""
        self.alarm: AlarmInternal = alarm
        self.state: AlarmStateInternal = state
        self.drive_now: datetime = now
        self.logger: AlarmLogger = logger
=======
    def __init__(self, state: AlarmStateInternal, now: datetime) -> None:
        self.state: AlarmStateInternal = state
        self.drive_now: datetime = now
>>>>>>> d2d7f4750c98bc7b8db33fdf03ac1e740a9fdc27
    # --------------------------------------------------------------
    # 🔹 repeat 設定に応じて、本当に鳴らして良いのかの最終判断
    # --------------------------------------------------------------
    def should_fire(self) -> bool:
        """本当に鳴らして良いのかの最終判断"""
<<<<<<< HEAD

        now: datetime = self.drive_now  # Manager が供給する内部クロック

        # 🔒 単発アラームの最終ガード
        if self.alarm.repeat == "single" and self.state.last_fired_at is not None:
            return False

        # ❶ 異常状態は即拒否（ログ対象）
        if self.state.is_invalid_state:
            self.logger.error(
                message=f"invalid state: {self.state}",
                where=self._where(func_name="should_fire"),
                alarm_id=self.alarm.id,
                context={
                    "state_id": self.state.id,
                    "next_fire": self.state.next_fire_datetime,
                    "repeat": self.alarm.repeat,
                    "now": now,
                    "state_triggered": self.state.triggered,
                    "state_last_fired_at": self.state.last_fired_at,
                },
                timestamp=now,
            )  # pylint: disable=fixme
=======
        now: datetime = self.drive_now  # Manager が供給する内部クロック

        # ❶ 異常状態は即拒否（ログ対象）
        if self.state.is_invalid_state:
            print(f"[エラー] 異常状態検出: next_fire_datetime={self.state.next_fire_datetime}, "
                  f"lifecycle_finished={self.state.lifecycle_finished}, id={self.state.id}")
>>>>>>> d2d7f4750c98bc7b8db33fdf03ac1e740a9fdc27
            return False

        # ❷ 未計算・終了状態は鳴らさない
        if self.state.is_uncomputed or self.state.is_finished:
            return False

        # ❸ 多重発火ガード（短時間）
        if self.state.last_fired_at:
<<<<<<< HEAD
            if (now - self.state.last_fired_at).total_seconds() < self.MULTI_FIRE_GUARD_SECONDS:
=======
            if (now - self.state.last_fired_at).total_seconds() < 5:
>>>>>>> d2d7f4750c98bc7b8db33fdf03ac1e740a9fdc27
                return False

        # ❹ 予定時刻に到達したか
        if self.state.next_fire_datetime is None:
            return False
<<<<<<< HEAD
        # ❺ 予定時刻が1分以上過去なら鳴らさない（遅延発火防止）
        if self.state.next_fire_datetime < self.drive_now - timedelta(minutes=1):
            return False
        # ❻ 予定時刻から2秒以内なら鳴らす
        fire_from: datetime = self.state.next_fire_datetime
        fire_until: datetime = fire_from + timedelta(seconds=self.FIRE_WINDOW_SECONDS)
        return fire_from <= self.drive_now <= fire_until

    def _where(self, func_name: str) -> "LogWhere":
        """Format location string for logging"""
        return LogWhere(module=__name__, function=func_name)
=======

        return now >= self.state.next_fire_datetime

>>>>>>> d2d7f4750c98bc7b8db33fdf03ac1e740a9fdc27
# =============================================================
