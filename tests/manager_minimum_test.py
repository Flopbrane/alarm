# -*- coding: utf-8 -*-
"""AlarmManagerCore の最小統合テスト

manager -> checker -> player の連動を、
副作用を抑えた最小構成で確認する。
"""
import unittest
from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import MagicMock

from alarm_payloads import AddPayload
from alarm_manager_cycle_control_options import CycleOptions
from alarm.alarm_manager import AlarmManager
from alarm_states_model import AlarmStateInternal
from alarm_ui_model import AlarmUI


class TestManagerMinimum(unittest.TestCase):
    """Facade 経由の AlarmManager の最小連動テスト"""

    def setUp(self) -> None:
        self.mgr = AlarmManager()

        # 外部副作用は持ち込まない
        self.mgr.player = cast(Any, MagicMock())
        self.player_play_mock: MagicMock = MagicMock()
        self.mgr.player.play = self.player_play_mock
        self.mgr.storage = MagicMock()
        self.mgr.logger = MagicMock()

        self.fire_cycle = CycleOptions(
            load=False,
            fire=True,
            save=False,
            notify=False,
            validate=True,
        )

        self.fixed_now = datetime(2026, 3, 25, 12, 0, 0)
        self.due_time: datetime = self.fixed_now + timedelta(minutes=1)

        # manager -> checker -> player を見たいので、
        # scheduler だけは固定値を返すようにして時刻条件を安定させる。
        self.mgr.scheduler.get_next_time = MagicMock(return_value=self.due_time)

    def _set_cycle_now(self, current: datetime) -> None:
        """manager の内部クロックを固定する"""
        def fake_tick() -> datetime:
            self.mgr._now = current
            return current

        self.mgr.tick = MagicMock(side_effect=fake_tick)

    def _new_ui_alarm(self) -> AlarmUI:
        """Facade 経由で流す新規登録用の UI データを作る"""
        return AlarmUI(
            name="minimum_test_alarm",
            date=self.fixed_now.strftime("%Y-%m-%d"),
            time=self.due_time.strftime("%H:%M"),
            repeat="single",
            enabled=True,
            sound="dummy.wav",
            duration=5,
        )

    def test_alarm_does_not_fire_before_due(self) -> None:
        """予定時刻前は checker が発火を許可しない"""
        self._set_cycle_now(self.fixed_now)

        self.mgr.apply_alarm_mutation("add", AddPayload(ui_alarm=self._new_ui_alarm()))
        self.mgr.start_cycle("loop", self.fire_cycle)

        state: AlarmStateInternal | None = self.mgr.states[0]
        self.assertIsNotNone(state.next_fire_datetime)
        self.assertEqual(state.next_fire_datetime, self.due_time)
        self.player_play_mock.assert_not_called()

    def test_alarm_flows_from_manager_to_checker_to_player(self) -> None:
        """予定時刻到達で manager -> checker -> player が連動する"""
        self._set_cycle_now(self.fixed_now)

        self.mgr.apply_alarm_mutation("add", AddPayload(ui_alarm=self._new_ui_alarm()))
        alarm = self.mgr.alarms[0]

        # 1サイクル目: 再計算だけ行い、次回鳴動予定を確定させる
        self.mgr.start_cycle("loop", self.fire_cycle)
        self.player_play_mock.assert_not_called()

        # 2サイクル目: 予定時刻に到達したので発火する
        self._set_cycle_now(self.due_time)
        self.mgr.start_cycle("loop", self.fire_cycle)

        self.player_play_mock.assert_called_once_with("dummy.wav", duration=5)

        state: AlarmStateInternal | None = self.mgr.get_state_by_id(alarm.id)
        self.assertIsNotNone(state)
        assert state is not None
        self.assertEqual(state.last_fired_at, self.due_time)
        self.assertTrue(state.lifecycle_finished)


if __name__ == "__main__":
    unittest.main()
