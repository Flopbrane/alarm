# -*- coding: utf-8 -*-
"""JSON dataclass(JSONモデル ↔ 永続化ストレージとの境界)"""
#########################
# Author: F.Kurokawa
# Description:
# JSON dataclass(JSONモデル ↔ 永続化ストレージとの境界)
#########################

# alarm_json_model.py
from __future__ import annotations

from collections.abc import Iterable

# 標準モジュール
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 自作モジュール
from constants import DEFAULT_SOUND


# ユーティリティ関数：list[int] のデフォルト値用
def _int_list() -> list[int]:
    return []


@dataclass
class AlarmJson:
    """アラーム設定を JSON 形式で保存・読み込みするためのデータクラス"""

    id: int
    name: str
    date: str  # "YYYY-MM-DD"
    time: str  # "HH:MM"
    repeat: str = "none"
    weekday: list[int] = field(default_factory=_int_list)
    week_of_month: list[int] = field(default_factory=_int_list)
    interval_weeks: int = 1
    base_date: str | None = None
    custom_desc: str = ""
    enabled: bool = True
    sound: str = field(default_factory=lambda: str(DEFAULT_SOUND))
    skip_holiday: bool = False
    duration: int = 10
    snooze_minutes: int = 10
    snooze_limit: int = 3

    @property
    def weekday_list(self) -> list[int]:
        """UI 側で iterable / CSV 等を扱うための補助プロパティ"""
        return list(self.weekday)

    @weekday_list.setter
    def weekday_list(self, v: list[int] | str | Iterable[int] | None) -> None:
        """UI / CSV / 外部入力の揺れを吸収するための補助 setter"""
        if not v:
            self.weekday = []
        elif isinstance(v, str):
            self.weekday = [int(x) for x in v.split(",")]
        else:
            self.weekday = list(v)

    @property
    def sound_path(self) -> Path:
        """sound の値を Path オブジェクトとして返す"""
        return Path(self.sound)


@dataclass
class AlarmStateJson:
    """アラーム状態を JSON 形式で保存・読み込みするためのデータクラス
    Json返しは必ず str | None
    Internal返しは必ず datetime | None
    str ↔ datetime 変換は必ず mapper で行う
    """

    id: int
    _snoozed_until: str | None = None
    _snooze_count: int = 0
    _triggered: bool = False
    _triggered_at: str | None = None
    # ★ 推奨追加！
    _last_fired_at: str | None = None
    _next_fire_datetime: str | None = None  # ISO8601 ("YYYY-MM-DDTHH:MM:SS")
    _lifecycle_finished: bool = False  # 鳴動開始後再参照終了フラグ(_next_fire_datetime更新後にリセット)

    # ===== Getter/Setter（こちらの方が自然で綺麗） =====
    @property
    def snoozed_until(self) -> str | None:
        """スヌーズ解除日時を取得"""
        return self._snoozed_until

    @snoozed_until.setter
    def snoozed_until(self, v: str | datetime | None) -> None:
        if v is None:
            self._snoozed_until = None
        elif isinstance(v, datetime):
            self._snoozed_until = v.isoformat()
        else:
            self._snoozed_until = v

    @property
    def snooze_count(self) -> int:
        """スヌーズ回数を取得"""
        return self._snooze_count

    @snooze_count.setter
    def snooze_count(self, v: int | str | None) -> None:
        if v is None:
            self._snooze_count = 0
        elif isinstance(v, str):
            self._snooze_count = int(v)
        else:
            self._snooze_count = v

    @property
    def triggered(self) -> bool:
        """アラームがトリガーされたかどうかを取得"""
        return self._triggered

    @triggered.setter
    def triggered(self, v: bool) -> None:
        self._triggered = v

    @property
    def triggered_at(self) -> str | None:
        """アラームがトリガーされた日時を取得"""
        if self._triggered_at is None:
            return None
        else:
            return self._triggered_at

    @triggered_at.setter
    def triggered_at(self, v: str | datetime | None) -> None:
        if v is None:
            self._triggered_at = None
        elif isinstance(v, datetime):
            self._triggered_at = v.isoformat()
        else:
            self._triggered_at = v

    @property
    def last_fired_at(self) -> str | None:
        """最後にアラームが鳴動した日時を取得"""
        if self._last_fired_at is None:
            return None
        else:
            return self._last_fired_at

    @last_fired_at.setter
    def last_fired_at(self, v: str | datetime | None) -> None:
        if v is None:
            self._last_fired_at = None
        elif isinstance(v, datetime):
            self._last_fired_at = v.isoformat()
        else:
            self._last_fired_at = v

    @property
    def next_fire_datetime(self) -> str | None:
        """次回鳴動予定日を取得"""
        return self._next_fire_datetime

    @next_fire_datetime.setter
    def next_fire_datetime(self, v: str | None) -> None:
        self._next_fire_datetime = v

    @property
    def lifecycle_finished(self) -> bool:
        """鳴動ライフサイクルが終了したかどうかを取得"""
        return self._lifecycle_finished

    @lifecycle_finished.setter
    def lifecycle_finished(self, v: bool) -> None:
        self._lifecycle_finished = v
# =========================================================
