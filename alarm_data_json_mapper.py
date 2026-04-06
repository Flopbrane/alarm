# -*- coding: utf-8 -*-
"""
保存JSONファイルから読み出してInternalモデルへ変換して、
alarm_manager.py へ受け渡すクラス群
=========================================================================
🔥 重要注意事項 🔥
Internal ↔ JSON dataclass 変換・受け渡し専用モジュール

【禁止事項】
- AlarmUI ↔ AlarmJson
- AlarmStateUI ↔ AlarmStateJson
上記の変換 mapper を作成してはならない。

【設計方針】
- datetime ↔ str の変換は mapper の責務とする。
- model の setter は不正値吸収の最終防御のみを担う。
- 変換ロジックを他の層に書くことは禁止する。

"""
#########################
# Author: F.Kurokawa
# Description:
# dataclass変換・受渡し(チェック済み)
#########################

# 標準ライブラリ
from typing import TYPE_CHECKING
from datetime import date, datetime

# 自作モジュール
from alarm_internal_model import AlarmInternal
from alarm_states_model import AlarmStateInternal
from alarm_json_model import AlarmJson, AlarmStateJson
from logs.log_app import get_logger
if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger


# ===============================
# 🔥 Datetime Utility（統一用）
# ===============================
def dt_to_str(dt: datetime | None) -> str | None: # 内部用
    """datetime → ISO8601 (T付き)"""
    return dt.isoformat() if dt else None


def str_to_dt(v: str | None) -> datetime | None:
    """str → datetime ※空白ならTに補正"""
    if not v:
        return None
    v = v.replace(" ", "T")  # 🔥 "YYYY-MM-DD HH:MM" も許容
    return datetime.fromisoformat(v)

def any_to_dt(v: str | datetime | None) -> datetime | None: # 内部値への変換用
    """str|datetime|None → datetime|None (安全ラッパー) ※ Json → Internal 専用。UI では使用禁止"""
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    return str_to_dt(v)

def dt_to_any(dt: datetime | None) -> str | None: # Jsonへの変換用
    """datetime|None → str|None (安全ラッパー) ※ Internal → Json 専用。UI では使用禁止"""
    if not dt:
        return None
    return dt.isoformat()

def logger() -> "AppLogger":
    """マッパーから共通ロガーを取得する"""
    return get_logger()

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
        """AlarmJson → AlarmInternal(str → datetime 変換含む)"""
        # 回避基準チェック
        if a is None:
            raise ValueError("AlarmJson が None か、あるいは、初回起動です。")
        # 日時チェック
        if not a.date or not a.time:
            raise ValueError(f"アラームの日時が無効です name={a.name} id={a.id}")

        # 発火基準 datetime（最重要）
        alarm_dt: datetime = datetime.fromisoformat(f"{a.date}T{a.time}")

        # 🔑 base_date は date-only → time を合成する
        base_dt: datetime | None = None

        if a.base_date:
            base_raw: datetime = datetime.fromisoformat(a.base_date)
            base_date_only: date = base_raw.date()  # ← time を必ず落とす
            base_dt = datetime.combine(
                base_date_only,
                alarm_dt.time()
            )

        alarm_internal = AlarmInternal(
            id=a.id,
            name=a.name,
            datetime_=alarm_dt,
            repeat=a.repeat,
            weekday=list(a.weekday),
            week_of_month=list(a.week_of_month),
            interval_weeks=a.interval_weeks,
            interval_days=a.interval_days,
            base_date_=base_dt,
            custom_desc=a.custom_desc,
            enabled=a.enabled,
            sound=a.sound_path,
            skip_holiday=a.skip_holiday,
            duration=a.duration,
            snooze_minutes=a.snooze_minutes,
            snooze_limit=a.snooze_limit,
            end_at=any_to_dt(a.end_at),
        )
        alarm_internal: AlarmInternal = self._repair_alarm(alarm_internal)
        return alarm_internal

    def _repair_alarm(self, alarm: AlarmInternal) -> AlarmInternal:

        if alarm.base_date_ is None:

            if isinstance(alarm.datetime_, datetime):
                alarm.base_date_ = alarm.datetime_

        return alarm

    # --------------------------------------------------------
    # 🔹 AlarmStateJson → AlarmStateInternal
    # --------------------------------------------------------
    def alarm_state_json_to_internal(self, s: AlarmStateJson) -> AlarmStateInternal:
        """AlarmStateJson → AlarmStateInternal"""
        state: AlarmStateInternal = AlarmStateInternal(id=s.id)
        state.snoozed_until=any_to_dt(s.snoozed_until)
        state.snooze_count=s.snooze_count
        state.triggered=s.triggered
        state.triggered_at=any_to_dt(s.triggered_at)
        state.last_fired_at=any_to_dt(s.last_fired_at)
        state.next_fire_datetime=any_to_dt(s.next_fire_datetime)
        state.lifecycle_finished=s.lifecycle_finished
        return state

# =========================================================
class InternalToJsonMapper(JsonToInternalMapper):
    """InternalモデルからJsonモデルへの変換クラス"""

    # -------------------------------------------------------
    # 🔹 AlarmInternal → AlarmJson
    # -------------------------------------------------------
    def alarm_internal_to_json(self, a: AlarmInternal) -> AlarmJson | None:
        """AlarmInternal → AlarmJson（ISO8601ベース）"""

        # datetime_ → ISO8601 → date / time 分離
        if not a.datetime_:
            log: AppLogger | None = logger()
            if log:
                log.warning(
                    message="AlarmInternal の datetime_ が None です。正確な繰り返し計算のためには、datetime_ を設定してください。",
                    alarm_id=a.id,
                    context={
                        "alarm_name": a.name,
                        "repeat": a.repeat,
                    },
                )
            print(f"AlarmInternal の datetime_ が無効です id={a.id} name={a.name}")    
            return None
        dt_iso: str = a.datetime_.isoformat(timespec="minutes")
        date_str: str
        time_str: str
        date_str, time_str = dt_iso.split("T")

        # base_date_ は date-only（YYYY-MM-DD）として保存
        base_date_str: str | None = (
            a.base_date_.date().isoformat() if a.base_date_ else None
        )
        # end_at は ISO8601 文字列 or None(None == 無期限)
        end_at_str: str | None = dt_to_any(a.end_at)

        return AlarmJson(
            id=a.id,
            name=a.name,
            date=date_str,
            time=time_str,
            repeat=a.repeat,
            weekday=list(a.weekday),
            week_of_month=list(a.week_of_month),
            interval_weeks=a.interval_weeks,
            interval_days=a.interval_days,
            base_date=base_date_str,
            custom_desc=a.custom_desc,
            enabled=a.enabled,
            sound=str(a.sound or ""),
            skip_holiday=a.skip_holiday,
            duration=a.duration,
            snooze_minutes=a.snooze_minutes,
            snooze_limit=a.snooze_limit,
            end_at=end_at_str,
        )

    # --------------------------------------------------------
    # 🔹 AlarmStateInternal → AlarmStateJson
    # --------------------------------------------------------
    def alarm_state_internal_to_json(
        self, s: AlarmStateInternal
    ) -> AlarmStateJson:
        """AlarmStateInternal → AlarmStateJson"""
        # NOTE:
        # is_invalid_state の検出・対処は Manager の責務。
        # mapper では状態をそのまま写す。
        j_state: AlarmStateJson = AlarmStateJson(id=s.id)
        j_state.snoozed_until=dt_to_any(s.snoozed_until)
        j_state.snooze_count=s.snooze_count
        j_state.triggered=s.triggered
        j_state.triggered_at=dt_to_any(s.triggered_at)
        j_state.last_fired_at=dt_to_any(s.last_fired_at)
        j_state.next_fire_datetime=dt_to_any(s.next_fire_datetime)
        j_state.lifecycle_finished=s.lifecycle_finished
        return j_state


# =========================================================
