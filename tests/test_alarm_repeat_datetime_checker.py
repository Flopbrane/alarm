# -*- coding: utf-8 -*-
"""Tests for AlarmDatetimeChecker"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock

from alarm_internal_model import AlarmInternal
from alarm_states_model import AlarmStateInternal
from alarm_repeat_datetime_checker import AlarmDatetimeChecker
from logs.multi_info_logger import AppLogger


class TestAlarmDatetimeChecker(unittest.TestCase):
    """Test cases for AlarmDatetimeChecker.should_fire()"""

    def setUp(self) -> None:
        """Set up common test data"""
        self.logger: MagicMock = MagicMock(spec=AppLogger)
        self.alarm = AlarmInternal(id="1", repeat="daily")
        self.now = datetime(2026, 3, 24, 9, 30, 0)

    def test_should_fire_with_invalid_state_logs_error(self) -> None:
        """Test that invalid state logs an error and returns False"""
        state = AlarmStateInternal(id="1")
        state.next_fire_datetime = datetime(2026, 3, 24, 9, 31, 0)
        state.lifecycle_finished = True

        self.assertTrue(state.is_invalid_state)

        checker = AlarmDatetimeChecker(self.alarm, state, self.now, self.logger)
        result: bool = checker.should_fire()

        self.assertFalse(result)
        self.logger.error.assert_called_once()
        kwargs = self.logger.error.call_args.kwargs
        self.assertEqual(kwargs["alarm_id"], self.alarm.id)
        self.assertEqual(kwargs["context"]["state_id"], state.id)

    def test_should_fire_with_valid_state_does_not_log_error(self) -> None:
        """Test that valid state does not log an error"""
        state = AlarmStateInternal(id="2")
        state.next_fire_datetime = datetime(2026, 3, 24, 9, 31, 0)
        state.lifecycle_finished = False

        self.assertFalse(state.is_invalid_state)

        checker = AlarmDatetimeChecker(self.alarm, state, self.now, self.logger)
        checker.should_fire()

        self.logger.error.assert_not_called()


if __name__ == "__main__":
    unittest.main()
