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
    from alarm.alarm_app import AlarmApp

def main(app: "AlarmApp") -> None:
    """CUI 起動エントリーポイント"""
    app.run_cui()
