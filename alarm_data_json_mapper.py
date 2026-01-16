# -*- coding: utf-8 -*-
"""
保存JSONファイルから読み出してInternalモデルへ変換して、
alarm_manager.py へ受け渡すクラス群
=========================================================================
🔥 重要注意事項 🔥
Internal↔JSON dataclass 変換・受渡し
(AlarmUI ↔ AlarmJsonのmappara,及び,
AlarmStateUI ↔ AlarmStateJson の変換mapper
絶対に作ったらダメなモジュール)
#########################
UI↔Internal, UIState↔InternalState の変換は重要だが
JSON↔UI, JSONState↔UIState の変換は,全体に作らないこと！！
"""

#########################
# Author: F.Kurokawa
# Description:
# dataclass変換・受渡し(チェック済み)
#########################
# 標準ライブラリ
from datetime import datetime

# 自作モジュール
from alarm_internal_model import AlarmInternal, AlarmStateInternal
from alarm_json_model import AlarmJson, AlarmStateJson


# ===============================
# 🔥 Datetime Utility（統一用）
# ===============================
def dt_to_str(dt: datetime | None) -> str | None:
    """datetime → ISO8601 (T付き)"""
    return dt.isoformat() if dt else None


def str_to_dt(v: str | None) -> datetime | None:
    """str → datetime ※空白ならTに補正"""
    if not v:
        return None
    v = v.replace(" ", "T")  # 🔥 "YYYY-MM-DD HH:MM" も許容
    return datetime.fromisoformat(v)

def any_to_dt(v: str | datetime | None) -> datetime | None:
    """str|datetime|None → datetime|None (安全ラッパー)"""
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    return str_to_dt(v)

# =========================================================
# 🔹 Jsonモデル → Internalモデル マッパー
# =========================================================
class JsonToInternalMapper:
    """JsonモデルからInternalモデルへの変換クラス"""
    # ----------------------------------------------
    # 🔹 AlarmJson → AlarmInternal
    # ----------------------------------------------
    def alarm_json_to_internal(
        self, a: AlarmJson | None
    ) -> AlarmInternal:
        """AlarmJson → AlarmInternal"""
        if a is None:
            raise ValueError("AlarmJson が None か、あるいは、初回起動です。")

        if not a.date or not a.time:
            raise ValueError(f"アラームの日時が無効です id={a.id}")

        dt: datetime | None = str_to_dt(f"{a.date}T{a.time}")

        if dt is None:
            raise ValueError(f"アラームの日時が無効です id={a.id}")
        return AlarmInternal(
            id=a.id,
            name=a.name,
            datetime_=dt,
            repeat=a.repeat,
            weekday=list(a.weekday),
            week_of_month=list(a.week_of_month),
            interval_weeks=a.interval_weeks,
            base_date_=str_to_dt(a.base_date),
            custom_desc=a.custom_desc,
            enabled=a.enabled,
            sound=a.sound_path,
            skip_holiday=a.skip_holiday,
            duration=a.duration,
            snooze_minutes=a.snooze_minutes,
            snooze_limit=a.snooze_limit,
        )

    # --------------------------------------------------------
    # 🔹 AlarmStateJson → AlarmStateInternal
    # --------------------------------------------------------
    def alarm_state_json_to_internal(self, s: AlarmStateJson) -> AlarmStateInternal:
        """AlarmStateJson → AlarmStateInternal"""
        return AlarmStateInternal(
            id=s.id,
            _snoozed_until=(
                any_to_dt(s.snoozed_until) if s.snoozed_until else None
            ),
            _snooze_count=s.snooze_count,
            _triggered=s.triggered,
            _triggered_at=any_to_dt(s.triggered_at) if s.triggered_at else None,
            _last_fired_at=(
                any_to_dt(s.last_fired_at) if s.last_fired_at else None
            ),
        )


class InternalToJsonMapper(JsonToInternalMapper):
    """InternalモデルからJsonモデルへの変換クラス"""

    # -------------------------------------------------------
    # 🔹 AlarmInternal → AlarmJson
    # -------------------------------------------------------
    def alarm_internal_to_json(self, a: AlarmInternal) -> AlarmJson:
        """AlarmInternal → AlarmJson"""
        # split combined datetime into date and time strings
        date_str: str = a.datetime_.date().strftime("%Y-%m-%d")
        time_str: str = a.datetime_.time().strftime("%H:%M")
        base_date_str: str | None = (
            a.base_date_.strftime("%Y-%m-%d") if a.base_date_ else None
        )

        return AlarmJson(
            id=a.id,
            name=a.name,
            date=date_str,
            time=time_str,
            repeat=a.repeat,
            weekday=list(a.weekday),
            week_of_month=list(a.week_of_month),
            interval_weeks=a.interval_weeks,
            base_date=base_date_str,
            custom_desc=a.custom_desc,
            enabled=a.enabled,
            sound=str(a.sound or ""),
            skip_holiday=a.skip_holiday,
            duration=a.duration,
            snooze_minutes=a.snooze_minutes,
            snooze_limit=a.snooze_limit,
        )
    # --------------------------------------------------------
    # 🔹 AlarmStateInternal → AlarmStateJson
    # --------------------------------------------------------
    def alarm_state_internal_to_json(
        self, s: AlarmStateInternal
    ) -> AlarmStateJson:
        """AlarmStateInternal → AlarmStateJson"""
        return AlarmStateJson(
            id=s.id,
            _snoozed_until=(
                dt_to_str(s.snoozed_until) if s.snoozed_until else None
            ),
            _snooze_count=s.snooze_count,
            _triggered=s.triggered,
            _triggered_at=(
                dt_to_str(s.triggered_at) if s.triggered_at else None
            ),
            _last_fired_at=(
                dt_to_str(s.last_fired_at) if s.last_fired_at else None
            ),
        )
# =========================================================
