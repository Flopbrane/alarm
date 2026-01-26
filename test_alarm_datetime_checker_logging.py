# -*- coding: utf-8 -*-
"""Test for invalid state logging in AlarmDatetimeChecker"""
import unittest
from datetime import datetime
from io import StringIO
import sys

from alarm_internal_model import AlarmStateInternal
from alarm_repeat_datetime_checker import AlarmDatetimeChecker


class TestAlarmDatetimeCheckerLogging(unittest.TestCase):
    """Test cases for AlarmDatetimeChecker invalid state logging"""

    def test_invalid_state_logs_error(self) -> None:
        """Test that invalid state triggers error logging"""
        # Create an invalid state: next_fire_datetime is NOT None AND lifecycle_finished is True
        state = AlarmStateInternal(id=42)
        state._next_fire_datetime = datetime(2025, 1, 15, 10, 30)
        state._lifecycle_finished = True
        
        # Verify it's detected as invalid
        self.assertTrue(state.is_invalid_state)
        
        # Capture print output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Create checker and call should_fire
        checker = AlarmDatetimeChecker(state=state, now=datetime.now())
        result = checker.should_fire()
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        
        # Verify should_fire returns False
        self.assertFalse(result)
        
        # Verify error was logged
        output = captured_output.getvalue()
        self.assertIn("[ERROR]", output)
        self.assertIn("Invalid alarm state detected", output)
        self.assertIn("id=42", output)
        self.assertIn("lifecycle_finished=True", output)

    def test_valid_state_no_error_log(self) -> None:
        """Test that valid state does not trigger error logging"""
        # Create a valid state
        state = AlarmStateInternal(id=1)
        state._next_fire_datetime = datetime(2025, 1, 15, 10, 30)
        state._lifecycle_finished = False
        
        # Verify it's not invalid
        self.assertFalse(state.is_invalid_state)
        
        # Capture print output
        captured_output = StringIO()
        sys.stdout = captured_output
        
        # Create checker and call should_fire
        checker = AlarmDatetimeChecker(state=state, now=datetime(2025, 1, 15, 10, 31))
        checker.should_fire()
        
        # Restore stdout
        sys.stdout = sys.__stdout__
        
        # Verify no error was logged for invalid state
        output = captured_output.getvalue()
        self.assertNotIn("Invalid alarm state detected", output)


if __name__ == "__main__":
    unittest.main()
