# -*- coding: utf-8 -*-
# pylint: disable=C0415
"""Application wiring for alarm startup."""
#########################
# Author: F.Kurokawa
# Description:
# AlarmManagerのインスタンス化の一元化
#########################
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from alarm.alarm_config_manager import Config, ConfigManager
from alarm.alarm_manager import AlarmManagerCore
from alarm.cui_controller import CUIController
from alarm.gui_controller import GUIController

if TYPE_CHECKING:
    from alarm.logger_bridge import AlarmLogger

@dataclass(slots=True)
class AlarmApp:
    """Owns the single AlarmManager instance and UI/controller wiring."""

    manager: "AlarmManagerCore"
    config_manager: ConfigManager
    config: Config

    def run_gui(self) -> None:
        """Start GUI with the shared manager."""
        from alarm.gui import AlarmGUI

        controller = GUIController(self.manager)
        gui = AlarmGUI(controller=controller)
        gui.start_gui()

    def run_cui(self) -> None:
        """Start CUI with the shared manager."""
        from alarm.cui import main as cui_main

        controller = CUIController(self.manager)
        cui_main(controller)


def create_alarm_app(logger: "AlarmLogger | None" = None) -> AlarmApp:
    """Create the shared manager and configuration wiring once."""
    manager: AlarmManagerCore = AlarmManagerCore(logger=logger)
    config_manager = ConfigManager()
    config: Config = config_manager.load_config()
    return AlarmApp(manager=manager, config_manager=config_manager, config=config)
