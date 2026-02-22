# -*- coding: utf-8 -*-
"""アラームの状態を保持するための dataclass 定義ファイル"""
#########################
from dataclasses import dataclass
from datetime import datetime
import typing



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

    id: str = ""  # 行識別子（必ず先頭）(UUIDに変更)
    _snoozed_until: datetime | None = None  # スヌーズ解除日時(一時的制御（短期）)
    _snooze_count: int = 0  # スヌーズ回数(スヌーズ制御（短期）)
    _triggered: bool = False  # 鳴動中か？(UI / 再生中判定)
    _triggered_at: datetime | None = None  # 鳴動開始時刻(履歴)
    _last_fired_at: datetime | None = None  # 直近の鳴動時刻(多重発火防止・履歴)
    # ★ 以下の二値を参考にして、checker, manager が動作を決定する
    _next_fire_datetime: datetime | None = (
        None  # 次回鳴動予定日(未来の確定スケジュール)
    )
    _lifecycle_finished: bool = (
        False  # 鳴動開始後再参照終了フラグ(_next_fire_datetime更新後にリセット)
    )
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
            _needs_recalc=False,
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
    def snoozed_until(self) -> typing.Optional[datetime]:
        """_snoozed_untilのgetter"""
        return self._snoozed_until

    @snoozed_until.setter  # setter:送られてきたデータを処理して保存する
    def snoozed_until(self, v: typing.Optional[datetime]) -> None:
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
    def triggered_at(self) -> typing.Optional[datetime]:
        """_triggered_atのgetter"""
        return self._triggered_at

    @triggered_at.setter
    def triggered_at(self, v: typing.Optional[datetime]) -> None:
        if v is None:
            self._triggered_at = None
            return
        self._triggered_at = v

    # ----------------------------------------------------
    # 🔥 last_fired_at（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property
    def last_fired_at(self) -> typing.Optional[datetime]:
        """_last_fired_atのgetter"""
        return self._last_fired_at

    @last_fired_at.setter
    def last_fired_at(self, v: typing.Optional[datetime]) -> None:
        if v is None:
            self._last_fired_at = None
            return
        self._last_fired_at = v

    # ----------------------------------------------------
    # 🔥 next_fire_datetime（文字列 → datetime 変換対応）
    # ----------------------------------------------------
    @property
    def next_fire_datetime(self) -> typing.Optional[datetime]:
        """_next_fire_datetimeのgetter"""
        return self._next_fire_datetime

    @next_fire_datetime.setter
    def next_fire_datetime(self, value: typing.Optional[typing.Union[datetime, str]]) -> None:
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
