# -*- coding: utf-8 -*-
"""GUI 起動エントリーポイント"""
#########################
# Author: F.Kurokawa
# Description:
# GUI_starter.py
#########################
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager


def main(
    manager: "AlarmManager",
) -> None:
    """GUI 起動エントリーポイント"""

    from gui_controller import GUIController

    GUIController(manager).start()
