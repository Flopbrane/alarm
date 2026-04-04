# -*- coding: utf-8 -*-
"""CUI 起動エントリーポイント"""
#########################
# Author: F.Kurokawa
# Description:
# CUIの呼び出しコントローラクラス
#########################

from alarm_manager_temp import AlarmManager
from logs.log_app import get_logger
from logs.multi_info_logger import AppLogger


def main() -> None:
    """CUI 起動エントリーポイント"""
    logger: AppLogger = get_logger()


    manager = AlarmManager(
        logger=logger,
    )

    from cui_controller import CUIController

    controller = CUIController(manager)
    controller.run()
