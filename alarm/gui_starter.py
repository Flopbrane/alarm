# -*- coding: utf-8 -*-
# pylint: disable=C0415
"""GUI 起動エントリーポイント"""
#########################
# Author: F.Kurokawa
# Description:
# GUI_starter.py
#########################
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alarm.alarm_app import AlarmApp


def main(
    app: "AlarmApp",
) -> None:
    """GUI 起動エントリーポイント"""
    app.run_gui()
