# -*- coding: utf-8 -*-
"""CUI 正規化ユーティリティのテスト"""
import unittest
from unittest.mock import MagicMock

from alarm_ui_mapper import UItoInternalMapper
from alarm_ui_model import AlarmUI
from data_ui_to_mgr_adapter import DataEditAdapter
from cui_repeat_normalizer import normalize_repeat_input
from cui_weekday_normalizer import normalize_weekday_list
from cui_datetime_normalizer import validate_date, validate_time


class TestCuiNormalizers(unittest.TestCase):
    """repeat / weekday の入力揺れを確認する"""

    def test_repeat_aliases(self) -> None:
        self.assertEqual(normalize_repeat_input("単発"), "single")
        self.assertEqual(normalize_repeat_input(" SINGLE "), "single")
        self.assertEqual(normalize_repeat_input("毎 日"), "daily")
        self.assertEqual(normalize_repeat_input("weekly"), "weekly")
        self.assertEqual(normalize_repeat_input("月次"), "monthly")
        self.assertEqual(normalize_repeat_input("日ごと"), "interval_days")
        self.assertEqual(normalize_repeat_input("カスタム"), "custom")

    def test_weekday_aliases(self) -> None:
        self.assertEqual(normalize_weekday_list("月,水,金"), [0, 2, 4])
        self.assertEqual(normalize_weekday_list("月曜、木曜、日曜"), [0, 3, 6])
        self.assertEqual(normalize_weekday_list("月曜日,木曜日,日曜日"), [0, 3, 6])
        self.assertEqual(normalize_weekday_list("mon,wed,sun"), [0, 2, 6])
        self.assertEqual(normalize_weekday_list("０、火,土"), [0, 1, 5])

    def test_normalized_alarm_ui_maps_to_alarm_internal(self) -> None:
        ui_alarm = AlarmUI(
            name="CUI integration",
            date=validate_date("2026/6/2") or "",
            time=validate_time("930") or "",
            repeat=normalize_repeat_input("毎 日"),
            weekday=normalize_weekday_list("月曜、木曜"),
            enabled=True,
            sound="dummy.wav",
            duration=5,
        )

        internal = UItoInternalMapper.ui_to_internal(ui_alarm)

        self.assertEqual(ui_alarm.date, "2026-06-02")
        self.assertEqual(ui_alarm.time, "09:30")
        self.assertEqual(ui_alarm.repeat, "daily")
        self.assertEqual(ui_alarm.weekday, [0, 3])

        self.assertIsNotNone(internal.datetime_)
        assert internal.datetime_ is not None
        self.assertEqual(internal.datetime_.isoformat(timespec="minutes"), "2026-06-02T09:30")
        self.assertEqual(internal.repeat, "daily")
        self.assertEqual(internal.weekday, [0, 3])

    def test_data_edit_adapter_passes_alarm_ui_to_manager(self) -> None:
        manager = MagicMock()
        adapter = DataEditAdapter(manager)
        ui_alarm = AlarmUI(
            name="Adapter bridge",
            date=validate_date("2026-06-03") or "",
            time=validate_time("07:15") or "",
            repeat=normalize_repeat_input("weekly"),
            weekday=normalize_weekday_list("mon,wed,sun"),
            enabled=True,
            sound="dummy.wav",
            duration=10,
        )

        adapter.add_alarm(ui_alarm)

        manager.apply_alarm_mutation.assert_called_once()
        call_args = manager.apply_alarm_mutation.call_args
        self.assertEqual(call_args.args[0], "add")
        payload = call_args.args[1]
        self.assertEqual(payload.ui_alarm.date, "2026-06-03")
        self.assertEqual(payload.ui_alarm.time, "07:15")
        self.assertEqual(payload.ui_alarm.repeat, "weekly")
        self.assertEqual(payload.ui_alarm.weekday, [0, 2, 6])


if __name__ == "__main__":
    unittest.main()
