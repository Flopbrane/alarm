# -*- coding: utf-8 -*-
"""CUI 起動エントリーポイント"""
#########################
# Author: F.Kurokawa
# Description:
# CUIの呼び出しコントローラクラス
#########################

from alarm_manager_temp import AlarmManager
from log_app import get_logger
from logs.multi_info_logger import AppLogger, new_trace_id


def main() -> None:
    """CUI 起動エントリーポイント"""
    logger: AppLogger = get_logger()
    trace_id: str = new_trace_id()

    manager = AlarmManager(
        logger=logger,
        trace_id=trace_id,
    )

    from cui_controller import CUIController

    controller = CUIController(manager)
    controller.run()
