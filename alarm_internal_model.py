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
from datetime import datetime, time, date as date_class
from pathlib import Path
from typing import Optional, Union

# 自作モジュール
from alarm_types import DateType, TimeType
from constants import DEFAULT_SOUND, REPEAT_INTERNAL

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
    id -> UUID に変更(str にする)
    """

    # =========================
    # 🔹 識別・表示系
    # =========================
    id: str = ""
    # 行識別子（必ず先頭）
    # JSON / GUI / 内部のすべてで共通の一意ID

    name: str = ""
    # 表示名（アラーム一覧・GUI表示用）
    # ロジック上の意味は持たない

    # =========================
    # 🔹 発火時刻の基準（最重要）
    # =========================
    datetime_: datetime | None = None
    # 🔑 【最重要フィールド】
    # このアラームが「何時に鳴るか」を決める唯一の基準
    #
    # - date / time プロパティはすべて、この値から派生
    # - Scheduler / Rule / Manager は必ずこれを参照する
    # - 「表示用の日時」ではなく「発火時刻の設計値」

    repeat: str = list(REPEAT_INTERNAL.values())[0]
    # 繰り返しの種類（意味だけを表す）
    # "single" / "daily" / "weekly" / "monthly" / "custom"
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

    interval_days: int | None = None
    # 何日おきか（2=2日おき、3=3日おき…）
    # repeat="days_span" で使用
    # repeat 内設定日の「数値パラメータ」

    # =========================
    # 🔹 カスタム設定（補助パラメータ）
    # =========================

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

    end_at: datetime | None = None
    # アラームの終了日時（指定日時以降は鳴らさない）
    # None の場合は無期限に鳴る

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
    # 「初期化__init__は dataclass に任せる。
    # でも、そのあとに“仕上げ処理”をしたい」
    # ----------------------------------------------------
    def __post_init__(self) -> None:
        """strで渡された sound を Path に変換する"""
        if not self.sound:
            self.sound = DEFAULT_SOUND
        elif isinstance(self.sound, str):
            self.sound = Path(self.sound)
    # ----------------------------------------------------
    # 🔥 time（TimeType）の getter/setter
    @property
    def date(self) -> DateType:
        """dateのgetter"""
        if self.datetime_ is None:
            return None
        return self.datetime_.date()

    @date.setter
    def date(self, v: DateType) -> None:
        """date を差し替える（時刻は保持）"""
        if v is None:
            self.datetime_ = None
            return

        if self.datetime_ is None:
            # 時刻がない場合は 00:00 を補完
            self.datetime_ = datetime.combine(v, time(0, 0))
        else:
            self.datetime_ = datetime.combine(v, self.datetime_.time())


    @property
    def time(self) -> TimeType:
        """timeのgetter（表示用）"""
        if self.datetime_ is None:
            return None
        return self.datetime_.time()


    @time.setter
    def time(self, v: TimeType) -> None:
        """time を差し替える（日付は保持）"""
        if v is None:
            return  # UI側で None を許さないなら何もしない

        if self.datetime_ is None:
            # 日付がない場合は「今日」を補完（または base_date）
            self.datetime_ = datetime.combine(date_class.today(), v)
        else:
            self.datetime_ = datetime.combine(self.datetime_.date(), v)

    # ----------------------------------------------------
    # 🔥 base_date_（文字列 → datetime 変換対応）
    # 🔥 repeat_base_datetime(base_date_)
    # ----------------------------------------------------
    @property
    def repeat_base_datetime(self) -> datetime | None:
        """
        繰り返し計算専用の基準日時
        ・weekly / custom / interval_weeks 用
        ・None の場合は datetime_ を基準とする
        """
        return self.base_date_ or self.datetime_

    @repeat_base_datetime.setter
    def repeat_base_datetime(self, v: datetime | None) -> None:
        """基準日時を設定（Internal では datetime のみ許可）"""
        self.base_date_ = v


@dataclass
class AlarmStateInternal:
    """アラーム状態を「状態＋予定」を持つクラスで保持するためのデータクラス
    【設計方針】
    id -> UUID に変更(str にする)
    Scheduler → next_fire_datetime を計算するだけ（※書き込みは Manager 経由）
    Checker → 今鳴らすか？を判断するだけ(読むだけ)
    Manager → lifecycle_finished を True にする唯一の存在(書き込み担当)
    【内部判定】
    - 内部ロジック（checkerが参照 / Managerが変更）
        next_fire_datetime == None & lifecycle_finished == False → 未計算
        → is_uncomputed() が True
        next_fire_datetime != None & lifecycle_finished == False → 次回予定あり
        → has_next_schedule() が True
        next_fire_datetime == None & lifecycle_finished == True  → 鳴動終了
        → is_finished() が True
        next_fire_datetime != None & lifecycle_finished == True  → エラー状態
        → is_invalid_state() が True
        _needs_recalc は Scheduler が参照 / 書き込み
    """

    id: str ="" # 行識別子（必ず先頭）(UUIDに変更)
    _snoozed_until: datetime | None = None  # スヌーズ解除日時(一時的制御（短期）)
    _snooze_count: int = 0  # スヌーズ回数(スヌーズ制御（短期）)
    _triggered: bool = False  # 鳴動中か？(UI / 再生中判定)
    _triggered_at: datetime | None = None  # 鳴動開始時刻(履歴)
    _last_fired_at: datetime | None = None  # 直近の鳴動時刻(多重発火防止・履歴)
    # ★ 以下の二値を参考にして、checker, manager が動作を決定する
    _next_fire_datetime: datetime | None = None  # 次回鳴動予定日(未来の確定スケジュール)
    _lifecycle_finished: bool = False  # 鳴動開始後再参照終了フラグ(_next_fire_datetime更新後にリセット)
    # ★ 追加: 再計算が必要かどうかのフラグ
    _needs_recalc: bool = False
    # _needs_recalc は、
    # 「この state は保存されているが、今は信用してはいけない」
    # という意思表示です。
    # つまり：
    # ❌ 壊れている
    # ❌ エラー
    # ⭕ 再計算待ち
    # この違いが非常に重要です。

    @classmethod
    def initial(cls, alarm_id: str) -> "AlarmStateInternal":
        """初期状態の AlarmStateInternal を生成する
        - alarm_id: 対応する AlarmInternal の id を指定する
        - すべての状態は「未計算・未鳴動」の初期値になる
        - これを生成してから Scheduler に渡すことで、
        Scheduler は「この状態は初期状態からスタートしている」と認識できる
        """
        return cls(
            id=alarm_id,
            _snoozed_until=None,
            _snooze_count=0,
            _triggered=False,
            _triggered_at=None,
            _last_fired_at=None,
            _next_fire_datetime=None,
            _lifecycle_finished=False,
                # ★ 追加
            _needs_recalc=False
        )

    # ===== Getter/Setter（こちらの方が自然で綺麗） =====
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
    def snoozed_until(self, v: Optional[datetime]) -> None:
        if v is None:
            self._snoozed_until = None
            return
        self._snoozed_until = v
        return

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
    def triggered_at(self, v: Optional[datetime]) -> None:
        if v is None:
            self._triggered_at = None
            return
        self._triggered_at = v
    # ----------------------------------------------------
    # 🔥 last_fired_at（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property
    def last_fired_at(self) -> Optional[datetime]:
        """_last_fired_atのgetter"""
        return self._last_fired_at

    @last_fired_at.setter
    def last_fired_at(self, v: Optional[datetime]) -> None:
        if v is None:
            self._last_fired_at = None
            return
        self._last_fired_at = v
    # ----------------------------------------------------
    # 🔥 next_fire_datetime（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property
    def next_fire_datetime(self) -> Optional[datetime]:
        """_next_fire_datetimeのgetter"""
        return self._next_fire_datetime

    @next_fire_datetime.setter
    def next_fire_datetime(self, value: Optional[Union[datetime, str]]) -> None:
        # None
        if value is None:
            self._next_fire_datetime = None
            return

        if isinstance(value, datetime):
            self._next_fire_datetime = value
            return

        try:
            # str 以外はここで TypeError が出る
            self._next_fire_datetime = datetime.fromisoformat(value)
            return
        except (TypeError, ValueError):
            try:
                self._next_fire_datetime = datetime.strptime(value, "%Y-%m-%d")
                return
            except (TypeError, ValueError):
                self._next_fire_datetime = None
            # その他の型（int, float, list, dict, etc）
            self._next_fire_datetime = None

    # ----------------------------------------------------
    # 🔥 lifecycle_finished（bool）:repeat == "single"の時の鳴動終了後の処置変数
    # ----------------------------------------------------
    @property
    def lifecycle_finished(self) -> bool:
        """_lifecycle_finishedのgetter"""
        return self._lifecycle_finished

    @lifecycle_finished.setter
    def lifecycle_finished(self, v: bool) -> None:
        self._lifecycle_finished = v
    # ----------------------------------------------------
    # 🔥 needs_recalc（bool）:再計算が必要かどうか
    # ----------------------------------------------------
    @property
    def needs_recalc(self) -> bool:
        """再計算が必要かどうかのフラグ"""
        return self._needs_recalc

    @needs_recalc.setter
    def needs_recalc(self, value: bool) -> None:
        self._needs_recalc = value
    ################################################################################
    # ===== 派生プロパティ =====
    ################################################################################
    # ===派生プロパティ（保存しない/状態を一目で理解出来るようにする）===

    @property
    def is_uncomputed(self) -> bool:
        """未計算状態かどうかを取得"""
        return self.next_fire_datetime is None and not self.lifecycle_finished

    @property
    def has_next_schedule(self) -> bool:
        """次回予定有りかどうかを取得"""
        return self.next_fire_datetime is not None and not self.lifecycle_finished

    @property
    def is_finished(self) -> bool:
        """鳴動終了状態かどうかを取得"""
        return self.next_fire_datetime is None and self.lifecycle_finished

    @property
    def is_invalid_state(self) -> bool:
        """本来起こらない状態（ガード・デバッグ用）"""
        return self.next_fire_datetime is not None and self.lifecycle_finished


# =========================================================
