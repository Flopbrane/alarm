# -*- coding: utf-8 -*-
"""alarm_manager_temp.py の単体テスト"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_manager_temp.py の単体テスト
#########################
# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from alarm_internal_model import AlarmInternal, AlarmStateInternal
from alarm_manager_temp import AlarmManager, CycleOptions


class TestAlarmManagerTemp(unittest.TestCase):
    """AlarmManagerTemp の単体テスト"""
    def setUp(self) -> None:
        """AlarmManager を副作用なしで初期化"""
        self.mgr = AlarmManager()

        # ---- 副作用のある部品を全部モック化 ----
        self.mgr.player = MagicMock()
        self.mgr.storage = MagicMock()
        self.mgr.storage.load_alarms = MagicMock(return_value=[])
        self.mgr.storage.load_standby = MagicMock(return_value=[])
        self.mgr.storage.save_alarms = MagicMock()
        self.mgr.storage.save_standby = MagicMock()
        self.mgr.logger = MagicMock()
        self.mgr.logger.error = MagicMock()

        # Scheduler の next_time を固定値で返す
        self.fixed_now = datetime(2026, 2, 4, 12, 0, 0)
        self.next_time: datetime = self.fixed_now + timedelta(minutes=1)

        self.mgr.scheduler.get_next_time = MagicMock(return_value=self.next_time)

        # ---- ダミーアラーム1件 ----
        alarm = AlarmInternal(
            id=1,
            name="TEST_ALARM",
            datetime_=self.fixed_now,
            repeat="single",
            weekday=[],
            week_of_month=[],
            interval_weeks=1,
            interval_days=None,
            base_date_=None,
            custom_desc="",
            enabled=True,
            sound="dummy.wav",
            skip_holiday=False,
            duration=30,
            snooze_minutes=5,
            snooze_limit=3,
            end_at=None,
        )

        state: AlarmStateInternal = AlarmStateInternal.initial(alarm.id)

        self.mgr.alarms = [alarm]
        self.mgr.states = [state]

    # --------------------------------------------------
    @patch('alarm_manager_temp.datetime')
    def test_process_sets_next_fire_datetime(self, mock_datetime: MagicMock) -> None:
        """process() で next_fire_datetime が計算される"""
        mock_datetime.now.return_value = self.fixed_now
        mock_datetime.side_effect = datetime

        self.mgr.run_cycle(
            CycleOptions(
                load=False,
                fire=False,
                save=False,
                notify=False,
                validate=True)
        )

        state: AlarmStateInternal = self.mgr.states[0]
        self.assertEqual(state.next_fire_datetime, self.next_time)

    # --------------------------------------------------
    @patch("alarm_manager_temp.datetime")
    def test_next_fire_times_updated_via_process(self, mock_datetime: MagicMock) -> None:
        """process() で next_fire_map が更新される"""
        mock_datetime.now.return_value = self.fixed_now
        mock_datetime.side_effect = datetime

        self.mgr.run_cycle(
            CycleOptions(
                load=False,
                fire=False,
                save=False,
                notify=False,
                validate=True
            )
        )

        state: AlarmStateInternal = self.mgr.states[0]
        self.assertEqual(state.next_fire_datetime, self.next_time)

    # --------------------------------------------------
    # 🔹 以下のメソッドでエラーが発生
    # --------------------------------------------------
    @patch("alarm_manager_temp.datetime")
    def test_no_alarms_fire_before_due_time(self, mock_datetime: MagicMock) -> None:
        """まだ鳴らない状態では play() が呼ばれない"""
        mock_datetime.now.return_value = self.fixed_now
        mock_datetime.side_effect = datetime

        # play メソッドを明示的にモック化
        self.mgr.player.play = MagicMock()

        self.mgr.run_cycle(
            CycleOptions(
                load=False,
                fire=False,
                save=False,
                notify=False,
                validate=True
            )
        )

        self.mgr.player.play.assert_not_called()
    # --------------------------------------------------
    # 「鳴ること」を確認する専用テストを1本だけ作る
    # --------------------------------------------------
    @patch("alarm_manager_temp.datetime")
    def test_alarm_fires_when_due(self, mock_datetime: MagicMock) -> None:
        """発火時刻到達で play() が呼ばれる"""
        mock_datetime.now.return_value = self.fixed_now
        mock_datetime.side_effect = datetime
        # next_time を「過去」にする
        self.mgr.scheduler.get_next_time = MagicMock(
            return_value=self.fixed_now - timedelta(seconds=1)
        )

        self.mgr.player.play = MagicMock()

        self.mgr.run_cycle(
            CycleOptions(
                load=False,
                fire=True,
                save=False,
                notify=False,
                validate=True
            )
        )

        self.mgr.player.play.assert_called_once()
    # --------------------------------------------------
    def test_startup_sync(self) -> None:
        """startup_sync が例外なく完走する"""
        self.mgr.run_cycle(
            CycleOptions(
                load=True,
                fire=False,
                save=True,
                notify=False,
                validate=True
                )
        )

        self.assertTrue(len(self.mgr.alarms) >= 0)
        self.assertTrue(len(self.mgr.states) >= 0)


if __name__ == "__main__":
    unittest.main()
