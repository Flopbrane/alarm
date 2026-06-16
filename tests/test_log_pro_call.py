# -*- coding: utf-8 -*-
"""アラームマネージャモジュール"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from typing import TYPE_CHECKING
from alarm.logger_bridge import get_alarm_logger


if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger


logger: "AppLogger" = get_alarm_logger()

logger.info(
    "alarm_project logger bridge test",
    context={
        "project": "alarm_project",
        "logger_backend": "logger_project",
    },
)
