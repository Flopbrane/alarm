# -*- coding: utf-8 -*-
""" アラームIDを UUID に移行するスクリプト """
#########################
# Author: F.Kurokawa
# Description:
# アラームIDを UUID に移行するスクリプト
#########################

from typing import TYPE_CHECKING
import uuid
if TYPE_CHECKING:
    from alarm_manager_temp import AlarmManager

def migrate_to_uuid(manager: "AlarmManager") -> None:
    """アラームIDを UUID に移行する"""
    # 1. 旧ID一覧を取得
    old_ids: set[str] = {a.id for a in manager.alarms}

    # 2. 新UUIDを割り当て
    id_map: dict[str, str] = {old_id: str(uuid.uuid4()) for old_id in old_ids}


    # 3. alarms / states を同時に書き換え
    for alarm in manager.alarms:
        alarm.id = id_map[alarm.id]

    for state in manager.states:
        state.id = id_map[state.id]

    # 4. 保存
    # AlarmManager に公開メソッドを追加するか、以下のように呼び出す
    manager.save()
    manager.save_standby()
