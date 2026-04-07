# -*- coding: utf-8 -*-
"""CUI 起動エントリーポイント"""
#########################
# Author: F.Kurokawa
# Description:
# CUIの呼び出しコントローラクラス
#########################
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager
    from logs.multi_info_logger import AppLogger

def main(manager: "AlarmManager") -> None:
    """CUI 起動エントリーポイント"""
    # manager.logger = get_logger()
    manager.logger.info("CUI 起動")

    # 循環参照回避のため、ここでインポート
    from cui_controller import CUIController  # pylint: disable=import-outside-toplevel

    controller = CUIController(manager)
    controller.run()
