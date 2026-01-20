# -*- coding: utf-8 -*-
"""dataclass 定義ファイル（アラーム設定・状態の内部形式）"""
#########################
# Author: F.Kurokawa
# Description:
# dataclass 定義ファイル（アラーム設定・状態の内部形式）
#########################

# alarm_internal_model.py
from __future__ import annotations

# 標準モジュール
from dataclasses import dataclass, field
from datetime import date as DateType
from datetime import datetime
from pathlib import Path
from typing import Optional

# 自作モジュール
from constants import DEFAULT_SOUND
from ui_datetime_normalizer import validate_time


# ユーティリティ関数：list[int] のデフォルト値用
def _int_list() -> list[int]:
    return []


@dataclass
class AlarmInternal:
    """
    アラーム設定を「内部ロジック用」に保持する dataclass

    【設計方針】
    - 内部ロジック（Scheduler / Rule / Manager）は
        「すべて datetime を基準」に動作する
    - 文字列（日付・時刻）は扱わない
    ★AlarmInternal の **「外部から触っていい属性一覧」**をコメントで書く
    ★Scheduler 側では _ 付き属性を 一切触らないと決める
    """

    # =========================
    # 🔹 識別・表示系
    # =========================
    id: int
    # 行識別子（必ず先頭）
    # JSON / GUI / 内部のすべてで共通の一意ID

    name: str
    # 表示名（アラーム一覧・GUI表示用）
    # ロジック上の意味は持たない

    # =========================
    # 🔹 発火時刻の基準（最重要）
    # =========================
    datetime_: datetime
    # 🔑 【最重要フィールド】
    # このアラームが「何時に鳴るか」を決める唯一の基準
    #
    # - date / time プロパティはすべて、この値から派生
    # - Scheduler / Rule / Manager は必ずこれを参照する
    # - 「表示用の日時」ではなく「発火時刻の設計値」

    repeat: str = "none"
    # 繰り返しの種類（意味だけを表す）
    # "none" / "daily" / "weekly" / "monthly" / "custom"
    #
    # ※ 何週おきかは interval_weeks が担当する

    # =========================
    # 🔹 繰り返し条件（補助パラメータ）
    # =========================
    weekday: list[int] = field(default_factory=_int_list)
    # 曜日指定（0=月〜6=日）
    # weekly / custom 用
    # 空リストの場合は曜日制限なし

    week_of_month: list[int] = field(default_factory=_int_list)
    # 第n週指定（1〜5）
    # custom 用

    interval_weeks: int = 1
    # 何週おきか（1=毎週、2=隔週、3=3週おき…）
    # repeat="weekly" / "custom" で使用
    # repeat の種類とは切り離された「数値パラメータ」

    base_date_: Optional[datetime] = None
    # 🔑 繰り返し計算専用の「基準日時」
    #
    # - weekly / custom / interval_weeks 用
    # - 「いつを起点に週数を数えるか」を決める
    # - 発火時刻そのものではない
    # - GUI表示用ではない
    #
    # 例：
    #   ・「2025/1/1 を基準に2週おき」
    #   ・「この日から隔週が始まる」

    custom_desc: str = ""
    # カスタム設定の説明文（GUI表示用）

    # =========================
    # 🔹 動作制御系
    # =========================
    enabled: bool = True
    # アラーム有効 / 無効フラグ

    sound: str | Path = DEFAULT_SOUND
    # 再生する音声ファイル
    # 内部では Path に正規化される

    skip_holiday: bool = False
    # 祝日スキップするか（Rule 側で使用）

    duration: int = 10
    # 再生秒数

    snooze_minutes: int = 10
    # 1回のスヌーズ時間（分）

    snooze_limit: int = 3
    # スヌーズ可能回数の上限

    # ====将来的に使用するproperty====
    # timezone_mode: Literal["local", "fixed"] = "local"
    # # 海外対応のproperty
    # timezone: str = "Asia/Tokyo"
    # # 海外対応のproperty
    # =========================

    # =========================
    # 🔹 repeat helper
    # =========================
    # ----------------------------------------------------
    # __post_init__ : sound を Path に変換
    #「初期化__init__は dataclass に任せる。
    # でも、そのあとに“仕上げ処理”をしたい」
    # ----------------------------------------------------
    def __post_init__(self) -> None:
        if not self.sound:
            self.sound = DEFAULT_SOUND
        elif isinstance(self.sound, str):
            self.sound = Path(self.sound)

    # ----------------------------------------------------
    # 🔥 date（YYYY-MM-DD）
    # ----------------------------------------------------
    @property
    def date(self) -> str:
        """dateのgetter"""
        return self.datetime_.strftime("%Y-%m-%d")

    @date.setter
    def date(self, v: str) -> None:
        if not v:
            v = datetime.now().strftime("%Y-%m-%d")

        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            print(f"[警告] 不正な日付入力: {v}")
            return

        t: str = self.datetime_.strftime("%H:%M")
        self.datetime_ = datetime.fromisoformat(f"{v}T{t}")

    # ----------------------------------------------------
    # 🔥 time（HH:MM）
    # ----------------------------------------------------
    @property
    def time(self) -> str:
        """timeのgetter"""
        return self.datetime_.strftime("%H:%M")

    @time.setter
    def time(self, t: str) -> None:
        if not t:
            t = datetime.now().strftime("%H:%M")

        if validate_time(t) is None:
            print(f"[警告] 不正な時刻入力: {t}")
            return

        d: str = self.datetime_.strftime("%Y-%m-%d")
        self.datetime_ = datetime.fromisoformat(f"{d}T{t}")

    # ----------------------------------------------------
    # 🔥 base_date_（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property
    def repeat_base_datetime(self) -> Optional[datetime]:
        """
        繰り返し計算専用の基準日時
        ・weekly / custom / interval_weeks 用
        ・発火時刻や表示日付とは無関係
        """
        return self.base_date_ or self.datetime_

    @repeat_base_datetime.setter
    def repeat_base_datetime(self, v: Optional[str | DateType | datetime]) -> None:
        """base_date_ を文字列/日付/datetime から正規化して設定する"""
        # None → None
        if v is None:
            self.base_date_ = None  # ← 既存ロジックを再利用
            return

        # datetime → そのまま
        if isinstance(v, datetime):
            self.base_date_ = v  # ← 既存ロジックを再利用
            return

        # date → 既存の時刻で補完
        if isinstance(v, DateType):
            self.base_date_ = datetime.combine(v, self.datetime_.time())
            return

        # str → 解析
        else:
            try:
                if " " in v:
                    self.base_date_ = datetime.fromisoformat(v.replace(" ", "T"))
                else:
                    self.base_date_ = datetime.fromisoformat(
                        f"{v}T{self.datetime_.time()}"
                    )
            except ValueError:
                print(f"[警告] 不正な base_date: {v}")
                self.base_date_ = None
                return


@dataclass
class AlarmStateInternal:
    """アラーム状態を「状態＋予定」を持つクラスで保持するためのデータクラス
    State は計算しない
    Scheduler が計算する
    Manager が書き込む
    """

    id: int = 0
    _snoozed_until: datetime | None = None  # スヌーズ解除日時(一時的制御（短期）)
    _snooze_count: int = 0  # スヌーズ回数(スヌーズ制御（短期）)
    _triggered: bool = False  # 鳴動中か？(UI / 再生中判定)
    _triggered_at: datetime | None = None  # 鳴動開始時刻(ログ・履歴)
    _last_fired_at: datetime | None = None  # 最終鳴動時刻(多重発火防止)
    _next_fire_datetime: datetime | None = (
        None  # 次回鳴動予定日(未来の確定スケジュール（中〜長期）)
    )

    @classmethod
    def initial(cls, alarm_id: int) -> "AlarmStateInternal":
        """初期状態の AlarmStateInternal を生成する"""
        return cls(
            id=alarm_id,
            _snoozed_until=None,
            _snooze_count=0,
            _triggered=False,
            _triggered_at=None,
            _last_fired_at=None,
            _next_fire_datetime=None,
        )

    # ===== Getter（こちらの方が自然で綺麗） =====
    # =========================
    # 🔹 ここに @property を置く！
    # =========================
    # NOTE: ログは将来 logger に置き換える
    # ----------------------------------------------------
    # 🔥 snoozed_until（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property  # getter:呼ばれてからデータを返す
    def snoozed_until(self) -> Optional[datetime]:
        """_snoozed_untilのgetter"""
        return self._snoozed_until

    @snoozed_until.setter  # setter:送られてきたデータを処理して保存する
    def snoozed_until(self, v: Optional[str | datetime]) -> None:
        if v is None:
            self._snoozed_until = None
            return

        if isinstance(v, datetime):
            self._snoozed_until = v
            return

        try:
            self._snoozed_until = datetime.fromisoformat(v)
        except (TypeError, ValueError):
            print(f"[警告] 不正な snoozed_until の値: {v}")
            self._snoozed_until = None

    @property
    def snooze_count(self) -> int:
        """_snooze_countのgetter"""
        return self._snooze_count

    @snooze_count.setter
    def snooze_count(self, v: int) -> None:
        self._snooze_count = v

    # ----------------------------------------------------
    # 🔥 triggered（bool）
    # ----------------------------------------------------
    @property
    def triggered(self) -> bool:
        """_triggeredのgetter"""
        return self._triggered

    @triggered.setter
    def triggered(self, v: bool) -> None:
        self._triggered = v

    # ----------------------------------------------------
    # 🔥 triggered_at（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property
    def triggered_at(self) -> Optional[datetime]:
        """_triggered_atのgetter"""
        return self._triggered_at

    @triggered_at.setter
    def triggered_at(self, v: Optional[str | datetime]) -> None:
        if v is None:
            self._triggered_at = None
            return

        if isinstance(v, datetime):
            self._triggered_at = v
            return

        try:
            self._triggered_at = datetime.fromisoformat(v)
        except (TypeError, ValueError):
            print(f"[警告] 不正な triggered_at の値: {v}")
            self._triggered_at = None

    # ----------------------------------------------------
    # 🔥 last_fired_at（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property
    def last_fired_at(self) -> Optional[datetime]:
        """_last_fierd_atのgetter"""
        return self._last_fired_at

    @last_fired_at.setter
    def last_fired_at(self, v: Optional[str | datetime]) -> None:
        if v is None:
            self._last_fired_at = None
            return

        if isinstance(v, datetime):
            self._last_fired_at = v
            return

        try:
            self._last_fired_at = datetime.fromisoformat(v)
        except (TypeError, ValueError):
            print(f"[警告] 不正な last_fired_at の値: {v}")
            self._last_fired_at = None
    @property
    def next_fire_datetime(self) -> Optional[datetime]:
        """_next_fire_datetimeのgetter"""
        return self._next_fire_datetime

    @next_fire_datetime.setter
    def next_fire_datetime(self, v: Optional[str | datetime]) -> None:
        if v is None:
            self._next_fire_datetime = None
            return

        if isinstance(v, datetime):
            self._next_fire_datetime = v
            return

        try:
            # v は "YYYY-MM-DD" を想定
            self._next_fire_datetime = datetime.fromisoformat(v)
        except (TypeError, ValueError):
            print(f"[警告] 不正な next_fire_datetime の値: {v}")
            self._next_fire_datetime = None
# =========================================================
