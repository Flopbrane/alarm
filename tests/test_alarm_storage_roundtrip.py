# -*- coding: utf-8 -*-
"""Facade 経由の AlarmManager で保存・再読込・発火を確認する統合テスト"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

from alarm.alarm_manager import AlarmManager, CycleOptions
from alarm_payloads import AddPayload
from alarm_states_model import AlarmStateInternal
from alarm_ui_model import AlarmUI


class TestAlarmStorageRoundTrip(unittest.TestCase):
    """AlarmInternal の JSON 往復と manager 発火を確認する"""

    def _set_cycle_now(self, manager: AlarmManager, current: datetime) -> None:
        def fake_tick() -> datetime:
            manager._now = current
            return current

        manager.tick = MagicMock(side_effect=fake_tick)

    def test_save_load_and_fire_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            alarm_path = tmp_dir / "alarms.json"
            standby_path = tmp_dir / "standby.json"

            fixed_now = datetime(2026, 6, 12, 9, 0, 0)
            due_time = fixed_now + timedelta(minutes=1)

            writer = AlarmManager(alarm_path=alarm_path, standby_path=standby_path)
            writer.logger = MagicMock()
            writer.player = cast(Any, MagicMock())
            writer.storage.logger = writer.logger
            self._set_cycle_now(writer, fixed_now)

            ui_alarm = AlarmUI(
                name="Round Trip Alarm",
                date=due_time.strftime("%Y-%m-%d"),
                time=due_time.strftime("%H:%M"),
                repeat="single",
                weekday=[],
                enabled=True,
                sound="dummy.wav",
                duration=5,
            )

            added = writer.apply_alarm_mutation("add", AddPayload(ui_alarm=ui_alarm))
            self.assertIsNotNone(added)
            self.assertTrue(alarm_path.exists())
            self.assertTrue(standby_path.exists())

            saved_alarm_data = json.loads(alarm_path.read_text(encoding="utf-8"))
            saved_standby_data = json.loads(standby_path.read_text(encoding="utf-8"))

            self.assertIn("alarms", saved_alarm_data)
            self.assertEqual(len(saved_alarm_data["alarms"]), 1)
            saved_alarm = saved_alarm_data["alarms"][0]
            self.assertIsInstance(saved_alarm["id"], str)
            self.assertEqual(saved_alarm["name"], "Round Trip Alarm")
            self.assertEqual(saved_alarm["date"], "2026-06-12")
            self.assertEqual(saved_alarm["time"], "09:01")
            self.assertEqual(saved_alarm["repeat"], "single")

            self.assertIn("standby", saved_standby_data)
            self.assertEqual(len(saved_standby_data["standby"]), 1)
            self.assertEqual(saved_standby_data["standby"][0]["id"], saved_alarm["id"])

            reader = AlarmManager(alarm_path=alarm_path, standby_path=standby_path)
            reader.logger = MagicMock()
            reader.storage.logger = reader.logger
            reader.player = cast(Any, MagicMock())
            reader.player.play = MagicMock()
            reader.scheduler.get_next_time = MagicMock(return_value=due_time)

            self._set_cycle_now(reader, fixed_now)
            reader.start_cycle(
                "startup",
                CycleOptions(
                    load=True,
                    fire=False,
                    save=False,
                    notify=False,
                    validate=True,
                ),
            )

            self.assertEqual(len(reader.alarms), 1)
            loaded_alarm = reader.alarms[0]
            self.assertEqual(loaded_alarm.id, saved_alarm["id"])
            self.assertEqual(loaded_alarm.name, "Round Trip Alarm")
            self.assertIsNotNone(loaded_alarm.datetime_)
            assert loaded_alarm.datetime_ is not None
            self.assertEqual(loaded_alarm.datetime_.isoformat(timespec="minutes"), "2026-06-12T09:01")

            loaded_state: AlarmStateInternal | None = reader.get_state_by_id(loaded_alarm.id)
            self.assertIsNotNone(loaded_state)
            assert loaded_state is not None
            self.assertEqual(loaded_state.next_fire_datetime, due_time)

            self._set_cycle_now(reader, due_time)
            reader.start_cycle(
                "loop",
                CycleOptions(
                    load=False,
                    fire=True,
                    save=False,
                    notify=False,
                    validate=True,
                ),
            )

            reader.player.play.assert_called_once_with("dummy.wav", duration=5)
            self.assertEqual(loaded_state.last_fired_at, due_time)
            self.assertTrue(loaded_state.lifecycle_finished)

    def test_alarm_ui_patch_updates_only_changed_fields_before_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_dir = Path(tmp_dir_str)
            alarm_path = tmp_dir / "alarms.json"
            standby_path = tmp_dir / "standby.json"

            manager = AlarmManager(alarm_path=alarm_path, standby_path=standby_path)
            manager.logger = MagicMock()
            manager.player = cast(Any, MagicMock())
            manager.storage.logger = manager.logger

            base_now = datetime(2026, 6, 12, 8, 0, 0)
            self._set_cycle_now(manager, base_now)

            added = manager.apply_alarm_mutation(
                "add",
                AddPayload(
                    ui_alarm=AlarmUI(
                        name="Patch Target",
                        date="2026-06-12",
                        time="08:30",
                        repeat="weekly",
                        weekday=[0, 2],
                        enabled=True,
                        sound="before.wav",
                        duration=10,
                    )
                ),
            )
            self.assertIsNotNone(added)
            assert added is not None

            from alarm_ui_model import AlarmUIPatch
            from alarm_payloads import UpdatePayload

            manager.apply_alarm_mutation(
                "update",
                UpdatePayload(
                    alarm_id=added.id,
                    patch=AlarmUIPatch(
                        time="09:45",
                        sound="after.wav",
                    ),
                ),
            )

            updated = manager.get_alarm_by_id(added.id)
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.name, "Patch Target")
            self.assertEqual(updated.repeat, "weekly")
            self.assertEqual(updated.weekday, [0, 2])
            self.assertEqual(str(updated.sound), "after.wav")
            self.assertIsNotNone(updated.datetime_)
            assert updated.datetime_ is not None
            self.assertEqual(updated.datetime_.isoformat(timespec="minutes"), "2026-06-12T09:45")

            saved_alarm_data = json.loads(alarm_path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved_alarm_data["alarms"]), 1)
            saved_alarm = saved_alarm_data["alarms"][0]

            self.assertEqual(saved_alarm["name"], "Patch Target")
            self.assertEqual(saved_alarm["repeat"], "weekly")
            self.assertEqual(saved_alarm["weekday"], [0, 2])
            self.assertEqual(saved_alarm["time"], "09:45")
            self.assertEqual(saved_alarm["sound"], "after.wav")
            self.assertNotIn("patch", saved_alarm)


if __name__ == "__main__":
    unittest.main()
