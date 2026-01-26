# -*- coding: utf-8 -*-
"""Tests for AlarmStateInternal.next_fire_datetime property"""
#########################
# Author: F.Kurokawa
# Description:
# AlarmStateInternal.next_fire_datetime プロパティのテストケース
#########################
# 標準モジュール
import unittest
from datetime import datetime

from alarm_internal_model import AlarmStateInternal


class TestNextFireDatetime(unittest.TestCase):
    """Test cases for AlarmStateInternal.next_fire_datetime property"""

    def setUp(self) -> None:
        """Initialize test fixture"""
        self.state = AlarmStateInternal(id=1)

    def test_setter_with_none(self) -> None:
        """Test setting next_fire_datetime to None"""
        self.state.next_fire_datetime = None
        self.assertIsNone(self.state.next_fire_datetime)

    def test_setter_with_datetime_object(self) -> None:
        """Test setting next_fire_datetime with datetime object"""
        dt = datetime(2025, 1, 15, 10, 30, 0)
        self.state.next_fire_datetime = dt
        self.assertEqual(self.state.next_fire_datetime, dt)

    def test_setter_with_iso_format_datetime_string(self) -> None:
        """Test setting next_fire_datetime with ISO format datetime string"""
        iso_str = "2025-01-15T10:30:00"
        self.state.next_fire_datetime = iso_str  # type: ignore
        self.assertEqual(self.state.next_fire_datetime, datetime(2025, 1, 15, 10, 30, 0))

    # def test_setter_with_date_only_string(self) -> None:
    #     """Test setting next_fire_datetime with date-only string"""
    #     date_str = "2025-01-15"
    #     self.state.next_fire_datetime = date_str  # type: ignore
    #     self.assertEqual(self.state.next_fire_datetime, datetime(2025, 1, 15, 0, 0, 0))

    def test_setter_with_invalid_string(self) -> None:
        """Test setting next_fire_datetime with invalid string"""
        invalid_str = "invalid-date"
        self.state.next_fire_datetime = invalid_str  # type: ignore
        self.assertIsNone(self.state.next_fire_datetime)

    def test_setter_with_invalid_type(self) -> None:
        """Test setting next_fire_datetime with invalid type"""
        self.state.next_fire_datetime = 12345  # type: ignore
        self.assertIsNone(self.state.next_fire_datetime)

    def test_getter_after_initialization(self) -> None:
        """Test getter returns None after initialization"""
        self.assertIsNone(self.state.next_fire_datetime)

    def test_multiple_assignments(self) -> None:
        """Test multiple sequential assignments"""
        dt1 = datetime(2025, 1, 15, 10, 30, 0)
        self.state.next_fire_datetime = dt1
        self.assertEqual(self.state.next_fire_datetime, dt1)

        dt2 = datetime(2025, 1, 20, 15, 45, 0)
        self.state.next_fire_datetime = dt2
        self.assertEqual(self.state.next_fire_datetime, dt2)

        self.state.next_fire_datetime = None
        self.assertIsNone(self.state.next_fire_datetime)

    def test_setter_with_microseconds(self) -> None:
        """Test setting next_fire_datetime with microseconds"""
        iso_str = "2025-01-15T10:30:45.123456"
        self.state.next_fire_datetime = iso_str  # type: ignore
        expected = datetime(2025, 1, 15, 10, 30, 45, 123456)
        self.assertEqual(self.state.next_fire_datetime, expected)


if __name__ == "__main__":
    unittest.main()
