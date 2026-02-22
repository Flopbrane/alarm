# -*- coding: utf-8 -*-
"""Tests for AlarmDatetimeChecker"""

import io
import sys
import unittest
from datetime import datetime

from alarm_states_model import AlarmStateInternal
from alarm_repeat_datetime_checker import AlarmDatetimeChecker


class TestAlarmDatetimeChecker(unittest.TestCase):
    """Test cases for AlarmDatetimeChecker.should_fire()"""

    def test_should_fire_with_invalid_state_logs_error(self) -> None:
        """Test that invalid state logs an error and returns False"""
        # Create a state with invalid configuration (next_fire_datetime set and lifecycle_finished True)
        state = AlarmStateInternal(id=1)
        state.next_fire_datetime = datetime(2025, 1, 15, 10, 30, 0)
        state.lifecycle_finished = True
        
        # Verify that this is indeed an invalid state
        self.assertTrue(state.is_invalid_state)
        
        # Capture stdout to check error logging
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create checker with the invalid state
        now = datetime(2025, 1, 15, 10, 30, 0)
        checker = AlarmDatetimeChecker(state, now)
        
        # Call should_fire() - it should return False
        result: bool = checker.should_fire()
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        
        # Verify the result is False
        self.assertFalse(result)
        
        # Verify error was logged
        output = captured_output.getvalue()
        self.assertIn("[エラー]", output)
        self.assertIn("異常状態検出", output)
        self.assertIn("next_fire_datetime=2025-01-15 10:30:00", output)
        self.assertIn("lifecycle_finished=True", output)
        self.assertIn("id=1", output)

    def test_should_fire_with_valid_state_does_not_log_error(self) -> None:
        """Test that valid state does not log an error"""
        # Create a state with valid configuration
        state = AlarmStateInternal(id=2)
        state.next_fire_datetime = datetime(2025, 1, 15, 10, 30, 0)
        state.lifecycle_finished = False
        
        # Verify that this is NOT an invalid state
        self.assertFalse(state.is_invalid_state)
        
        # Capture stdout to check no error is logged
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Create checker with the valid state
        now = datetime(2025, 1, 15, 10, 30, 0)
        checker = AlarmDatetimeChecker(state, now)
        
        # Call should_fire() - it should check other conditions
        result: bool = checker.should_fire()
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        
        # Verify no error was logged
        output = captured_output.getvalue()
        self.assertNotIn("[エラー]", output)
        self.assertNotIn("異常状態検出", output)


if __name__ == "__main__":
    unittest.main()
