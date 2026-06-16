# -*- coding: utf-8 -*-
"""アラームの追加・更新・削除のペイロード定義ファイル
manager と UIController 間でやり取りされるペイロードの型定義を行う"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from dataclasses import dataclass

from alarm_ui_model import AlarmUI, AlarmUIPatch

@dataclass
class AddPayload:
    """型ヒントの定義"""
    ui_alarm: AlarmUI


@dataclass
class UpdatePayload:
    """型ヒントの定義"""
    alarm_id: str
    patch: AlarmUIPatch


@dataclass
class DeletePayload:
    """型ヒントの定義"""
    alarm_id_list: list[str]
