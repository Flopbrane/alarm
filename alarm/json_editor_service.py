# -*- coding: utf-8 -*-
"""JSONファイルの読み書きを行うサービスクラス"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from alarm.constants import DEFAULT_SOUND

ALARM_TEMPLATE: dict[str, Any] = {
    "id": 0,
    "name": "",
    "date": "",
    "time": "",
    "repeat": "none",
    "weekday": [],
    "week_of_month": [],
    "interval_weeks": 1,
    "interval_days": 0,
    "base_date": "",
    "enabled": True,
    "custom_desc": "",
    "sound": str(DEFAULT_SOUND),
    "skip_holiday": False,
    "duration": 10,
    "snooze_minutes": 10,
    "snooze_limit": 3,
    "end_at": "",
    "_snooze_count": 0,
    "_snoozed_until": "",
    "_triggered": False,
    "_triggered_at": "",
    "_last_fired_at": "",
}

ALARM_KEYS: list[str] = list(ALARM_TEMPLATE.keys())


def read_text_file(path: str | Path) -> str:
    """UTF-8 テキストを読み込む。"""
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def save_alarm_editor_json(
    path: str | Path,
    snooze_default: int,
    alarms: list[dict[str, Any]],
) -> None:
    """json_editor 用の保存をアトミックに行う。"""
    payload = {
        "snooze_default": snooze_default,
        "alarms": alarms,
    }

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target.parent,
        delete=False,
        suffix=".tmp",
    ) as tmp_file:
        json.dump(payload, tmp_file, ensure_ascii=False, indent=4)
        tmp_name = tmp_file.name

    os.replace(tmp_name, target)
