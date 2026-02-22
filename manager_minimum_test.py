# -*- coding: utf-8 -*-
import time

from datetime import datetime, timedelta
from alarm_manager_temp import AlarmManager

mgr = AlarmManager()

alarm_time: datetime = datetime.now() + timedelta(seconds=50)

mgr.start_cycle(
    name="test_alarm",
    datetime_=alarm_time,
)

print("alarm set:", alarm_time)

mgr.start_cycle("startup")

while True:

    mgr.start_cycle("loop")
    time.sleep(1)
