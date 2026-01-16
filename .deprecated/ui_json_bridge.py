# -*- coding: utf-8 -*-
"""UIモデルからJSONモデルへの変換ラッパー"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################

import alarm_ui_mapper
from alarm_model import AlarmJson, AlarmStateJson
from alarm_ui_model import AlarmStateUI, AlarmUI


# ラッパー：alarm_ui_mapper の実装名差異に対応する軽い橋渡し
def ui_to_json(ui_alarm: AlarmUI) -> AlarmJson:
    """AlarmUI → AlarmJson"""
    if hasattr(alarm_ui_mapper, "ui_to_json"):
        return alarm_ui_mapper.ui_to_json(ui_alarm)
    raise ImportError("alarm_ui_mapperはui_to_json関数を提供していません")


def stateui_to_statejson(gui_state: AlarmStateUI) -> AlarmStateJson:
    """AlarmStateUI → AlarmStateJson"""
    if hasattr(alarm_ui_mapper, "stateui_to_statejson"):
        return alarm_ui_mapper.stateui_to_statejson(gui_state)
    raise ImportError("alarm_ui_mapper は stateui_to_statejson 関数を提供していません")
