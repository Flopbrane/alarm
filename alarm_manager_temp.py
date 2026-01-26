# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""アラームマネージャの一時退避モジュール
alarm + now + actual_now → state
更新、次回鳴動日時更新、発火判定、鳴動制御
(アラーム管理の役割)
"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_manager_temp.py
#########################
# Future improvements:
# - 正規化系（_normalize_on_boot_and_edit）を別モジュール化候補
# - state 操作系の切り出し検討

# Standard library
import inspect
import sys
import threading
import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import CodeType, FrameType
from typing import Any, Callable, Literal, Optional, TypedDict

# Local modules
from alarm_data_json_mapper import InternalToJsonMapper, JsonToInternalMapper
from alarm_internal_model import AlarmInternal, AlarmStateInternal
from alarm_irregular_logger import AlarmLogger, LogWhere
from alarm_json_model import AlarmJson, AlarmStateJson
from alarm_manager_cycle_controll_options import (
    CONFIG_CHANGED,
    RUNNING,
    STARTUP,
    CycleOptions,
)
from alarm_player import AlarmPlayer
from alarm_repeat_datetime_checker import AlarmDatetimeChecker
from alarm_scheduler import AlarmScheduler
from alarm_storage import AlarmStorage
from alarm_ui_mapper import (
    InternaltoUIMapper,
    UItoInternalMapper,
    UIpatchtoInternalMapper,
)
from alarm_ui_model import AlarmUI, AlarmUIPatch
from env_paths import ALARM_PATH, BACKUP_DIR, DATA_DIR, STANDBY_PATH


class NextAlarmInfo(TypedDict):
    """型ヒントの定義"""

    alarm: AlarmInternal
    next_datetime: datetime
    time_until: float


class AlarmManager:
    """アラーム設定を管理するクラス（STOP制御統一版）"""

    _MAX_BACKUPS = 3
    SnoozeResult = Literal["none", "expired", "limit"]
    # "none": 何もしない
    # "expired": 時刻到達で解除（次を鳴らして良い）
    # "limit": 回数オーバー解除（強制終了）
    CycleCondition = Literal["startup", "loop", "config_change"]
    # "startup": ソフト起動時
    # "loop": 通常ループ
    # "config_change": 設定変更時

    @staticmethod
    def get_base_dir() -> Path:
        """PyInstaller or Python 実行フォルダ"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    # ======================================================
    # 初期化
    # ======================================================
    def __init__(
        self,
        alarm_path: Path | None = None,
        standby_path: Path | None = None,
    ) -> None:
        # === paths ===
        self.base_dir: Path = self.get_base_dir()
        self.alarm_file_path: Path = (
            alarm_path if alarm_path is not None else ALARM_PATH
        )
        self.standby_path: Path = standby_path or STANDBY_PATH
        self.backup_dir: Path = BACKUP_DIR
        self.data_dir: Path = DATA_DIR

        # === internal model ===
        self.alarms: list[AlarmInternal] = []
        self.states: list[AlarmStateInternal] = []
        # === settings ===
        self.snooze_default: int = 10
        self._stop_requested: bool = False
        self._last_stop_time: datetime | None = None

        # === mapper ===
        self.json_to_internal_mapper = JsonToInternalMapper()
        self.internal_to_json_mapper = InternalToJsonMapper()
        self.ui_to_internal_mapper = UItoInternalMapper()
        self.internal_to_ui_mapper = InternaltoUIMapper()
        self.ui_patch_to_internal_mapper = UIpatchtoInternalMapper()
        # === core ===
        self.player = AlarmPlayer()
        self.storage = AlarmStorage()
        self.scheduler = AlarmScheduler()
        # === time ===
        # _now は「1サイクル内で共有される現在時刻」
        # internal_clock() からのみ設定される
        self._now: datetime | None = None
        # ソフト起動時刻（内部クロック基準）
        self._boot_datetime: datetime = self.internal_clock()
        # === runtime ===
        # dict{alarm_id:state.next_fire_datetime}
        self._next_fire_map: dict[str, datetime] = {}
        # このサイクルで新規作成されたアラームIDリスト
        self._just_created_id_list: list[str] = []
        # === GUI / UI 更新通知用リスナー ===
        self._listeners: list[Callable[[], None]] = []
        # === irregular logger ===
        self.logger = AlarmLogger(log_dir=self.base_dir / "logs")

    # ======================================================
    # 🔹 AlarmManager 内部クロック管理(ソフト内基準日時)
    # ======================================================
    # 音楽でたとえると 🎵
    # ・tick()
    # 👉 指揮者が「今からテンポ120で行くぞ」と合図する
    # ・internal_clock()
    # 👉 演奏者が「今は120だな」と確認する
    # main_loop は 指揮者なので、
    # テンポを決める必要がある。
    def tick(self) -> None:
        """1ループ開始時に一度だけ now を確定する"""
        self._now = datetime.now().replace(microsecond=0)

    def internal_clock(self) -> datetime:
        """AlarmManager 内部で一貫して使用する現在時刻を返す"""
        if self._now is None:
            self.tick()
        assert self._now is not None  # ← 型チェッカーへの宣言
        return self._now
        # self._nowがNoneではない(=self._nowがセット済)場合、self._nowを返す。(1cycle,1tickの原則は崩れない)
        # self._nowがNoneの場合、self.tick()を呼び出して現在時刻をセットし、その後self._nowを返す。

    # ======================================================
    # 🔹 AlarmStateInternal関係の更新処理
    # ======================================================
    def _where(self, method_name: str) -> LogWhere:
        """ログ用の位置情報を生成する（呼び出し元を指す）"""
        frame: FrameType | None = inspect.currentframe()
        caller: FrameType | None = frame.f_back if frame else None  # ← 1つ上

        lineno: int | Any = caller.f_lineno if caller else -1
        code: CodeType | None = caller.f_code if caller else None
        where: LogWhere = {
            "line": lineno,
            "module": code.co_filename if code else __name__,
            "file": code.co_filename if code else "",
            "class_name": self.__class__.__name__,
            "method_name": method_name,
            "function": code.co_name if code else method_name,
        }
        return where

    def _recalc_states(self) -> None:
        """状態の正規化と next_fire_datetime 再計算（副作用なし）"""
        now: datetime = self.internal_clock()

        for alarm in self.alarms:
            state: AlarmStateInternal | None = self._get_state(alarm.id)

            # 終了済みは触らない
            if state is not None and state.lifecycle_finished:
                continue
            # 無効アラームは触らない
            if alarm.enabled is False:
                continue

            if state is None:
                state = self._get_or_create_state(alarm.id)
                self.logger.warning(
                    message="State not found, created new state",
                    where=self._where(method_name="_recalc_states"),
                    alarm_id=alarm.id,
                    context={},
                    timestamp=now,
                )
                self._just_created_id_list.append(alarm.id)

            # 再計算が必要 or 未計算
            if state.needs_recalc or state.is_uncomputed:
                next_dt: datetime | None = self.scheduler.get_next_time(alarm, now)
                state.next_fire_datetime = next_dt
                state.needs_recalc = False

    def _get_state(self, alarm_id: str) -> AlarmStateInternal | None:
        """alarm_id に対応する AlarmStateInternal を取得"""
        for state in self.states:
            if state.id == alarm_id:
                return state
        return None

    def get_alarm_by_id(self, alarm_id: str) -> AlarmInternal | None:
        """alarm_id に対応する AlarmInternal を取得"""
        for alarm in self.alarms:
            if alarm.id == alarm_id:
                return alarm
        return None

    def get_state_by_id(self, alarm_id: str) -> AlarmStateInternal | None:
        """alarm_id に対応する AlarmStateInternal を取得"""
        for state in self.states:
            if state.id == alarm_id:
                return state
        return None


    def _update_next_fire_runtime(self) -> None:
        """state から next_fire_map を再構築（ソート込み）"""
        # 先に alarm を辞書化して O(1) 参照にする
        alarm_by_id: dict[str, AlarmInternal] = {a.id: a for a in self.alarms}

        pairs: list[tuple[str, datetime]] = []
        for state in self.states:
            next_dt: datetime | None = state.next_fire_datetime
            if next_dt is None or state.lifecycle_finished:
                continue

            alarm: AlarmInternal | None = alarm_by_id.get(state.id)
            if alarm is None or not alarm.enabled:
                continue

            pairs.append((state.id, next_dt))

        self._next_fire_map = dict(sorted(pairs, key=lambda x: x[1]))

    def _handle_due_alarms(self) -> None:  # 実際に鳴らす処理
        """次回鳴動予定日時に達したアラームを処理する（自己修復型）"""

        now: datetime = self.internal_clock()

        for alarm_id, next_fire_dt in self._next_fire_map.items():
            alarm: AlarmInternal | None = self.get_alarm_by_id(alarm_id)
            # state が無ければ作る（初回・破損対応）
            state: AlarmStateInternal = self._get_or_create_state(alarm_id)

            if alarm is None:
                self.logger.warning(
                    message="Alarm not found in alarms list, skipping",
                    where=self._where(method_name="_handle_due_alarms"),
                    alarm_id=alarm_id,
                    context={},
                    timestamp=now,
                )
                continue

            # 🔒 lifecycle_finished / disabled は完全に対象外
            # 新規 state (lifecycle_finished=False) はここを通過する
            if state.lifecycle_finished:
                continue
            if not alarm.enabled:
                continue

            # next_fire_datetime 未計算 or 不整合 → 再計算
            recalculated = False

            if state.next_fire_datetime is None and not state.is_uncomputed:
                recalculated = True
            elif state.next_fire_datetime != next_fire_dt:
                recalculated = True

            if recalculated:
                new_next: datetime | None = self.scheduler.get_next_time(
                    alarm=alarm, now=now
                )

                if new_next is None:
                    self.logger.error(
                        message=f"alarm_id={alarm_id} 次回鳴動日時を再計算できません（無効扱い）",
                        where=self._where(method_name="_handle_due_alarms"),
                        alarm_id=alarm_id,
                        context={},
                        timestamp=now,
                    )
                    continue

                self.logger.info(
                    message=f"alarm_id={alarm_id} next_fire_datetime を再計算しました",
                    where=self._where(method_name="_handle_due_alarms"),
                    alarm_id=alarm_id,
                )
                state.next_fire_datetime = new_next

            # 最終判定
            checker = AlarmDatetimeChecker(
                alarm=alarm, state=state, now=now, logger=self.logger
            )
            new_state_id: str = state.id
            if checker.should_fire() and new_state_id not in self._just_created_id_list:
                self._fire_alarm(alarm, state)

    def _get_or_create_state(self, alarm_id: str) -> AlarmStateInternal:
        """alarm_id に対応する state を必ず返す（無ければ生成）"""
        for state in self.states:
            if state.id == alarm_id:
                return state
        # 無ければ新規作成（自己修復）
        new_state: AlarmStateInternal = AlarmStateInternal.initial(alarm_id)
        self.states.append(new_state)
        # 新規作成された state はこのサイクルでは鳴らさない
        self._just_created_id_list.append(alarm_id)
        return new_state

    def _build_sorted_next_alarm_list(self) -> list[tuple[str, datetime]]:
        """次回鳴動予定日時のリストをソートして返す"""
        return sorted(self._next_fire_map.items(), key=lambda x: x[1])

    def _fire_alarm(self, alarm: AlarmInternal, state: AlarmStateInternal) -> None:
        """アラームを発火させる"""
        # 発火処理
        self.player.play(str(alarm.sound), duration=alarm.duration)

        # state 更新
        now: datetime = self.internal_clock()
        state.triggered = True
        state.triggered_at = now
        state.last_fired_at = now
        state.needs_recalc = True
        # single 繰り返しは寿命終了扱いにする
        if alarm.repeat == "single":
            state.lifecycle_finished = True
            state.next_fire_datetime = None
            state.needs_recalc = False
        # ログ出力
        self.logger.info(
            message="Alarm fire check",
            where=self._where(method_name="_fire_alarm"),
            alarm_id=alarm.id,
            context={
                "state_id": state.id,
                "next_fire": state.next_fire_datetime,
                "repeat": alarm.repeat,
                "now": now,
                "state_triggered": state.triggered,
                "state_last_fired_at": state.last_fired_at,
            },
            timestamp=now,
        )
        # ログ出力などの通知
        print(f"Alarm Fired: {alarm.name} at {now.isoformat()}")

    def _check_invalid_states(self) -> None:
        """不正なアラーム状態をチェックしてログ出力する"""
        now: datetime = self.internal_clock()

        for state in self.states:
            if state.is_invalid_state:
                self.logger.error(
                    message="Invalid alarm state",
                    where=self._where(method_name="_check_invalid_states"),
                    alarm_id=state.id,
                    context={
                        "value": {
                            "next_fire_datetime": state.next_fire_datetime,
                            "lifecycle_finished": state.lifecycle_finished,
                        },
                        "types": {
                            "next_fire_datetime": type(
                                state.next_fire_datetime
                            ).__name__,
                            "lifecycle_finished": type(
                                state.lifecycle_finished
                            ).__name__,
                        },
                    },
                    timestamp=now,  # ← ここが基準時刻
                )

    def _repair_invalid_states(self) -> None:
        """不正なアラーム状態を修復する"""
        now: datetime = self.internal_clock()

        for state in self.states:
            if state.is_invalid_state:
                self.logger.warning(
                    message="Repairing invalid alarm state",
                    where=self._where(method_name="_repair_invalid_states"),
                    alarm_id=state.id,
                    context={
                        "before": {
                            "next_fire_datetime": state.next_fire_datetime,
                            "lifecycle_finished": state.lifecycle_finished,
                        },
                    },
                    timestamp=now,
                )
                # 修復処理
                if state.next_fire_datetime is not None:
                    state.next_fire_datetime = None

                alarm: AlarmInternal | None = self.get_alarm_by_id(state.id)
                if (
                    alarm
                    and alarm.repeat == "single"
                    and state.triggered_at is not None
                    and state.triggered_at < now
                ):
                    # single 繰り返しで既に鳴動済みなら寿命終了扱いにする
                    state.triggered = False
                    state.lifecycle_finished = True
                    state.next_fire_datetime = None
                    state.needs_recalc = False

                self.logger.warning(
                    message="Repaired invalid alarm state",
                    where=self._where(method_name="_repair_invalid_states"),
                    alarm_id=state.id,
                    context={
                        "after": {
                            "next_fire_datetime": state.next_fire_datetime,
                            "lifecycle_finished": state.lifecycle_finished,
                        },
                    },
                    timestamp=now,
                )

    # ======================================================
    # 🔹 ========== 移植したメソッド ============
    # ======================================================

    # ======================================================
    # フィールド更新
    # ======================================================
    # まず決めるべき「ルール」📐（重要）
    # 編集時のフィールド更新ルールを
    # 黒川さん仕様として 明文化 します。
    #
    # 🔹 編集後の state の扱いルール（おすすめ）
    # ・triggered / snoozed は解除
    # ・スヌーズ回数はリセット
    # ・last_fired_at は保持してもよい
    # ・id は絶対に変更しない
    #
    # 理由：
    # 編集は「未来の挙動」を変える行為であり、
    # 過去ログ（last_fired_at）は消す必要なし

    def _normalize_on_boot_and_edit(self, reason: Literal["boot", "edit"]) -> None:
        boot: datetime = self._boot_datetime
        targets: list[AlarmStateInternal] = []

        if reason == "boot":
            # 過去に取り残された state を拾う
            for state in self.states:
                if (
                    not state.lifecycle_finished
                    and state.next_fire_datetime is not None
                    and state.next_fire_datetime
                    < boot  # 起動時点で過去にある → 異常状態
                ):
                    targets.append(state)

        elif reason == "edit":
            # 編集により影響を受ける state を拾う
            for state in self.states:
                if state.id not in self._just_created_id_list:
                    targets.append(state)

        # 共通処理
        for state in targets:
            self._reset_state_for_future(state)

        print(f"target_list: {[s.id for s in targets]}")
        print(f"_just_created_id_list: {self._just_created_id_list}")

        # 再計算は一括で1回だけ
        if targets:
            self._recalc_states()
            for state in targets:
                state.needs_recalc = False

    def _reset_state_for_future(self, state: AlarmStateInternal) -> None:
        """未来の挙動に合わせて state をリセットする"""
        state.snoozed_until = None
        state.snooze_count = 0
        state.triggered = False
        state.triggered_at = None
        state.needs_recalc = True
        # last_fired_at は保持（ログとして有用）

    def apply_alarm_mutation(
        self,
        action: Literal["add", "update", "delete"],
        payload: Any,
    ) -> None:
        """★編集処理の入口は apply_alarm_mutation だけ★"""
        # 1. 実処理
        if action == "add":
            self._add_alarm(payload)
        elif action == "update":
            alarm_id: str
            patch: AlarmUIPatch
            alarm_id, patch = payload
            self._update_alarm(alarm_id, patch)
        elif action == "delete":
            self._delete_alarms(payload)
        else:
            raise ValueError(action)

        # 2. 編集イベント発生を通知（ここが肝）
        self._normalize_on_boot_and_edit(reason="edit")

        # 3. 保存
        self._save()
        self._save_standby()

    # ======================================================
    # 🔹 編集後の next_fire_datetime の扱いルール（必須）
    # ======================================================
    def _update_alarm(self, alarm_id: str, patch: AlarmUIPatch) -> None:
        """実在アラームデータが、部分的に変更された場合の編集処理"""
        # 1. 既存 alarm を取得
        alarm: AlarmInternal | None = self.get_alarm_by_id(alarm_id)
        if alarm is None:
            raise KeyError(f"Alarm not found: id={alarm_id}")

        # 2. 既存 alarm → UI（編集前ベース）
        base_ui: AlarmUI = self.internal_to_ui_mapper.internal_to_ui(alarm)

        # 3. UI の上書き（変更された部分だけ）
        merged_ui: AlarmUI = self._merge_ui(base_ui, patch)

        # 4. UI → Internal 変換
        new_internal: AlarmInternal = self.ui_to_internal_mapper.ui_to_internal(merged_ui)
        new_internal.id = alarm.id  # ← ここは完全に自明

        # 5. alarm を置き換え
        self._replace_alarm(new_internal)

        # 6. state を調整
        self._adjust_state_after_update(alarm_id)

        # 7. 正規化
        self._normalize_on_boot_and_edit(reason="edit")

        # 8. 保存 & 通知
        self._save()
        self._save_standby()
        self._notify_listeners()

    def _adjust_state_after_update(self, alarm_id: str) -> None:
        """アラーム編集後に state を安全な状態へ調整する(state_resetter)"""

        # state を必ず取得（なければ生成）
        state: AlarmStateInternal = self._get_or_create_state(alarm_id)

        # この時点で state は AlarmStateInternal であることが保証される

        # --- 編集後は状態をリセット ---
        state.snoozed_until = None
        state.snooze_count = 0
        state.triggered = False
        state.triggered_at = None
        # ★重要：編集＝未来が変わる → 再計算必須
        state.needs_recalc = True
        # last_fired_at は保持（ログとして有用）

    def _merge_ui(self, base: AlarmUI, patch: AlarmUIPatch) -> AlarmUI:
        merged: AlarmUI = base

        for field_name, value in patch.__dict__.items():
            if field_name == "id":
                continue
            if value is not None:
                merged = replace(
                    merged, **{field_name: value}
                )  # dataclassのreplaceを使用してフィールドを更新

        return merged

    # =====================================================
    # 🔹 UUIDの発行メソッド
    # =====================================================
    def get_next_id(self) -> str:
        """次のアラームIDを取得"""
        return str(uuid.uuid4())

    # ======================================================
    # 🔹 新規データの追加
    # ======================================================
    def _add_alarm(self, ui_alarm: AlarmUI) -> Optional[AlarmInternal]:
        """新規アラームを追加する"""

        # 1. ID を決定（Manager の責務）
        alarm_id: str = self.get_next_id()

        # 2. UI → Internal 変換
        try:
            internal: AlarmInternal = self.ui_to_internal_mapper.ui_to_internal(
                ui_alarm
            )
        except (ValueError, TypeError) as e:
            print(f"[エラー] アラーム変換失敗: {e}")
            # ここで失敗したら「登録できなかった」と明示的に返す
            self.logger.error(
                message=f"アラーム変換失敗: {e}",
                where=self._where(method_name="add_alarm"),
                alarm_id=None,  # ← 正直で正確(logger側でUNASSIGNED扱い)
                context={"error": str(e)},
                timestamp=self.internal_clock(),
            )
            return None

        # 3. ID を正式に付与
        internal.id = alarm_id

        # 4. alarms に登録
        self.alarms.append(internal)

        # 5. state を初期状態で生成（必ず id を揃える）
        self._get_or_create_state(alarm_id)

        # 6. 永続化・通知
        self._save()
        self._notify_listeners()

        return internal

    def _replace_alarm(self, new_internal: AlarmInternal) -> None:
        """内部リストのアラームを置換または追加し、対応する state を保証する"""
        # 同じ id の alarm があれば置換
        for idx, a in enumerate(self.alarms):
            if a.id == new_internal.id:
                self.alarms[idx] = new_internal
                break
        else:
            # 見つからなければ追加
            self.alarms.append(new_internal)

        # 同じ id の state が既にあるなら何もしない.なければ新しく追加する.
        for s in self.states:
            if s.id == new_internal.id:
                return
        self._get_or_create_state(new_internal.id)

    # ======================================================
    # 🔹 アラーム削除
    # ======================================================
    # GUI一覧表から、複数のアラームデータを削除する
    def _delete_alarms(self, ids: list[str]) -> None:
        """GUI複数削除"""
        self._remove_alarms_by_ids(set(ids))

    # 内部制御
    def _remove_alarms_by_ids(self, ids: set[str]) -> None:
        """内部専用：ID集合でアラームを削除"""
        # 「指定されたIDのアラームを、
        # alarm と state の両方から、
        # idsに含まれていない物を残して新規のリストを作成する
        # ー＞idsに含まれている物は削除される」
        self.alarms = [a for a in self.alarms if a.id not in ids]
        self.states = [s for s in self.states if s.id not in ids]
        self._save()
        self._save_standby()
        self._notify_listeners()

    # ======================================================
    # GUI通知
    # ======================================================
    def _notify_listeners(self) -> None:
        """GUI や CUI が「状態が変わったら呼んでほしい関数」
        を登録しておくためのリストです
        「関数（コールバック）」そのものです"""
        if not hasattr(self, "_listeners"):
            self._listeners = []

        def _run() -> None:
            for func in self._listeners:
                try:
                    func()
                except Exception as e:
                    self.logger.error(
                        message=f"Listener error: {e!r}",
                        where=self._where(method_name="_notify_listeners"),
                        alarm_id=None,
                        context={"error": str(e)},
                        timestamp=self.internal_clock(),
                    )
                    print(f"⚠️ リスナーエラー: {e!r}")

        threading.Thread(target=_run, daemon=True).start()

    def add_listener(self, func: Callable[[], None]) -> None:
        """GUI通知"""
        if func not in self._listeners:
            self._listeners.append(func)

    def remove_listener(self, func: Callable[[], None]) -> None:
        """GUI通知"""
        if func in self._listeners:
            self._listeners.remove(func)

    # ======================================================
    # ON/OFF
    # ======================================================
    def toggle_alarm(self, alarm_id: str) -> None:
        """アラーム ON/OFF"""
        for a in self.alarms:
            if a.id == alarm_id:
                a.enabled = not a.enabled
                break
        self._save()
        self._notify_listeners()

    # ======================================================
    # スヌーズ解除判定
    # ======================================================
    def _check_snooze(
        self, alarm: AlarmInternal, state: AlarmStateInternal, now: datetime
    ) -> "SnoozeResult":
        """スヌーズ解除判定
        "none": 何もしない
        "expired": 時刻到達で解除（次を鳴らして良い）
        "limit": 回数オーバー解除（強制終了）"""

        su: datetime | None = state.snoozed_until
        if su is None:
            return "none"

        # snooze_limit is stored on the AlarmInternal;
        # prefer the alarm resolved by id if available.
        stored_alarm: AlarmInternal | None = self.get_alarm_by_id(state.id)
        target_alarm: AlarmInternal = (
            stored_alarm if stored_alarm is not None else alarm
        )
        snooze_limit: Any | int = getattr(
            target_alarm, "snooze_limit", self.snooze_default
        )

        # 回数オーバー → 強制解除（今後の扱いを呼び出し側に伝える）
        if state.snooze_count >= snooze_limit:
            state.snoozed_until = None
            state.snooze_count = 0
            state.triggered = False
            state.triggered_at = None
            return "limit"

        # 時刻到達 → 通常解除（次を鳴らして良い）
        if now >= su.replace(second=0, microsecond=0):
            state.snoozed_until = None
            return "expired"

        return "none"

    # ======================================================
    # スヌーズ
    # ======================================================
    def snooze_alarm(
        self,
        alarm: AlarmInternal,
        state: AlarmStateInternal,
        minutes: int | None = None,
    ) -> None:
        """アラームをスヌーズ"""
        now: datetime = self.internal_clock()
        minutes = minutes or alarm.snooze_minutes
        base: datetime = now.replace(second=0, microsecond=0)
        next_time: datetime = base + timedelta(minutes=minutes)

        state.snoozed_until = next_time
        state.snooze_count += 1
        state.triggered = False
        state.triggered_at = None

        self._save()
        self._save_standby()

    # ======================================================
    # STOP
    # ======================================================
    def request_stop(self) -> None:
        """アラーム停止要求"""
        self._stop_requested = True
        self._last_stop_time = self.internal_clock()

    def stop_alarm(self, state: AlarmStateInternal) -> None:
        """アラーム停止 → スヌーズ情報クリア"""
        state.snoozed_until = None
        state.snooze_count = 0
        state.triggered = False
        state.triggered_at = None

        # 多重発火防止：直後に再発火しないよう数秒 ahead にしておく
        state.last_fired_at = (self.internal_clock()) + timedelta(seconds=10)

        self._save()
        self.request_stop()
        self._save_standby()

    # ======================================================
    # 現在のアラーム判定(GUI表示用)
    # ======================================================
    def get_active_alarm_state(self) -> Optional[AlarmStateInternal]:
        """スヌーズ中 or 直前に鳴ったアラームを返す"""

        # 1. スヌーズ中のアラーム（最優先）
        for state in self.states:
            if state.snoozed_until:
                return state

        # 2. triggered_at があるアラームを抽出
        fired: list[AlarmStateInternal] = [
            a for a in self.states if a.triggered and a.triggered_at
        ]

        if not fired:
            return None

        # Pylance対策：keyは常に datetime を返す
        return max(fired, key=lambda a: a.triggered_at or datetime.min)

    # ======================================================
    # 読み込み/保存エリア
    # ======================================================
    # -----------------------------------------
    # 🔹 alarms.json のみ読み込む
    # -----------------------------------------
    def load_alarms(self) -> list[AlarmInternal]:
        """alarms.json を読み込み、self.alarms に反映する"""
        json_alarms: list[AlarmJson] = self.storage.load_alarms()
        if not json_alarms:
            self.alarms = []
            return self.alarms

        self.alarms = [
            self.json_to_internal_mapper.alarm_json_to_internal(a) for a in json_alarms
        ]
        return self.alarms

    # -----------------------------------------
    # 🔹 standby.json のみ読み込む
    # -----------------------------------------
    def load_standby(self) -> list[AlarmStateInternal]:
        """standby.json だけ読み込んで self.alarms の内部状態に反映する"""
        json_states: list[AlarmStateJson] = self.storage.load_standby()
        if not json_states:
            return []

        # Convert standby JSON entries to internal state dataclasses
        self.states = [
            self.json_to_internal_mapper.alarm_state_json_to_internal(s)
            for s in json_states
        ]

        # Ensure there's a state entry for every registered alarm
        existing_ids: set[str] = {s.id for s in self.states}
        for alarm in self.alarms:
            if alarm.id not in existing_ids:
                self.states.append(self._get_or_create_state(alarm.id))
                self.logger.info(
                    message="State auto-created",
                    where=self._where(method_name="load_standby"),
                    alarm_id=alarm.id,
                )
        return self.states

    # -----------------------------------------
    # 🔹 alarms.json , standby.json
    # -----------------------------------------
    def load_all(self) -> None:
        """互換性用: alarms.json と standby.json を両方読み込み、state を整合させる"""
        # Load alarms and standby using existing loaders
        self.load_alarms()
        self.load_standby()

        # Ensure there's a state entry for every registered alarm
        self._ensure_state_id_integrity()

        # Persist standby to ensure consistency on disk
        self._save_standby()

    # ======================================================
    # 保存
    # ======================================================
    def _save(self) -> None:
        """alarms.json を保存する（standby と同レベルで正規化）"""
        alarms_by_id: dict[str, AlarmInternal] = {}

        for alarm in self.alarms:
            alarms_by_id[alarm.id] = alarm  # 後勝ち

        # state に存在しない alarm を除外したい場合はここで絞れる
        valid_ids: set[str] = {s.id for s in self.states}
        normalized: list[AlarmInternal] = [
            a for a in alarms_by_id.values()
            if a.id in valid_ids
            ]

        json_alarms: list[AlarmJson] = [
            self.internal_to_json_mapper.alarm_internal_to_json(a)
            for a in normalized
            ]

        self.storage.save_alarms(json_alarms)

    def _save_standby(self) -> None:
        """standby.json を保存する（alarms と同レベルで正規化）"""
        normalized: list[AlarmStateInternal] = self._normalize_for_persistence()

        json_states: list[AlarmStateJson] = [
            self.internal_to_json_mapper.alarm_state_internal_to_json(s) for s in normalized
        ]

        self.storage.save_standby(json_states)
        self.states = normalized  # ← 保存後に正規化された状態を反映する（自己修復）

    # ======================================================
    # 🔹 状態正規化ユーティリティ
    # ======================================================
    def _ensure_state_id_integrity(self) -> None:
        """alarms を正として state を整合させる（ID対応のみ）"""
        # 実行中の軽量自己修復（★id対応のみ、日時計算はしない）
        # alarms にある id は必ず state に存在させる
        # alarms に無い state は削除する
        # 👉 「ID 対応の保証」だけ
        # 👉 日時計算・trigger・lifecycle には触らない

        # alarms 側の id 集合（正）
        valid_ids: set[str] = {a.id for a in self.alarms}

        # 既存 states を id で潰す（後勝ち）
        states_by_id: dict[str, AlarmStateInternal] = {}
        for s in self.states:
            if s.id in valid_ids:  # alarms に無い state は捨てる
                states_by_id[s.id] = s

        # alarms にあるのに state が無い → 生成
        for alarm in self.alarms:
            if alarm.id not in states_by_id:
                states_by_id[alarm.id] = self._get_or_create_state(alarm.id)

        # alarms の順序に合わせて並べ直す（デバッグしやすい）
        self.states = [states_by_id[a.id] for a in self.alarms]

    def _normalize_for_persistence(self) -> list[AlarmStateInternal]:
        """→ 保存専用・検証・一括整合用"""
        # 永続化のための正規化
        # 保存前に欠けた state を補完
        # 保存前にalarms に存在しない state を除外
        states_by_id: dict[str, AlarmStateInternal] = {s.id: s for s in self.states}
        # 1) alarms にあるのに state が無い → 生成
        for alarm in self.alarms:
            if alarm.id not in states_by_id:
                states_by_id[alarm.id] = self._get_or_create_state(alarm.id)
        # 2) alarms に無い state は除外
        valid_ids: set[str] = {a.id for a in self.alarms}
        return [s for s in states_by_id.values() if s.id in valid_ids]

    def _normalize_alarms_by_id(self) -> None:
        """alarms を id で潰す（後勝ち）"""
        unique: dict[str, AlarmInternal] = {}
        for alarm in self.alarms:
            unique[alarm.id] = alarm
        self.alarms = list(unique.values())

    # ======================================================
    # ======================================================
    # 🔹 サイクル開始の入り口（公開API）
    # ======================================================
    # ======================================================
    def start_cycle(self, condition: CycleCondition) -> None:
        """AlarmManager 公開API：サイクル開始"""

        if condition == "startup":
            self._start_startup_cycle()
        elif condition == "loop":
            self._start_running_cycle()
        elif condition == "config_change":
            self._start_config_changed_cycle()

    # ======================================================
    # 🔹 設定変更後の再計算
    # ======================================================
    def _start_config_changed_cycle(self) -> None:
        """アラーム設定変更後の再計算処理"""
        self.run_cycle(CONFIG_CHANGED)

    # ======================================================
    # 🔹 起動直後の「状態正規化」
    # ======================================================
    def _start_startup_cycle(self) -> None:
        """起動直後の状態正規化処理"""
        self.run_cycle(STARTUP)

    # ======================================================
    # 🔹 メインループ
    # ======================================================
    def _start_running_cycle(self) -> None:
        """メインループ処理"""
        self.run_cycle(RUNNING)

    # ======================================================
    # 🔹 manager駆動の入り口
    # ======================================================

    def run_cycle(self, opt: CycleOptions) -> None:
        """AlarmManager の1サイクル処理（内部エンジン）"""

        # ==================================================
        # ① 内部クロック確定（1 cycle = 1 now）
        # ==================================================
        self._begin_cycle()

        # ==================================================
        # ② ロード & 整合化
        # ==================================================
        if opt.load:
            self._load_phase()

        # ==================================================
        # ③ 状態修復・再計算
        # ==================================================
        self._recalc_phase()

        # ==================================================
        # ④ 発火判定・鳴動
        # ==================================================
        if opt.fire:
            self._fire_phase()

        # ==================================================
        # ⑤ 永続化
        # ==================================================
        if opt.save:
            self._save_phase()

        # ==================================================
        # ⑥ 通知・検証
        # ==================================================
        if opt.notify:
            self._notify_listeners()

        if opt.validate:
            self._check_invalid_states()

        # ==================================================
        # ⑦ STOP 処理
        # ==================================================
        self._stop_phase()

    # ① cycle開始
    def _begin_cycle(self) -> None:
        self.tick()

    # ② loadフェーズ
    def _load_phase(self) -> None:
        self.load_all()

    # ③ 再計算フェーズ（超重要）
    def _recalc_phase(self) -> None:
        self._repair_invalid_states()
        self._recalc_states()
        self._update_next_fire_runtime()

    # ④ 発火フェーズ
    def _fire_phase(self) -> None:
        self._handle_due_alarms()

    # ⑤ 保存フェーズ（例外を吸収）
    def _save_phase(self) -> None:
        """「state は壊れやすい」「alarms は主データ」
        という意味で、
        standby → alarms の順は 心理的にも安全 なので、今の順でOKです。"""
        # 0) 保存前の最終正規化（ここが肝）
        self._normalize_alarms_by_id()
        self._ensure_state_id_integrity()
        # 1) 保存処理（例外を吸収してログ出力）
        try:
            self._save_standby()
        except (OSError, IOError, ValueError) as e:
            self.logger.error(
                message="Failed to save standby state",
                where=self._where(method_name="_save_phase"),
                alarm_id="UNASSIGNED",
                context={"error": str(e)},
                timestamp=self.internal_clock(),
            )
        # 2) alarms.json の保存は、standby.json より後にする（ここが肝）
        try:
            self._save()
        except (OSError, IOError, ValueError) as e:
            self.logger.error(
                message="Failed to save alarms data",
                where=self._where(method_name="_save_phase"),
                alarm_id="UNASSIGNED",
                context={"error": str(e)},
                timestamp=self.internal_clock(),
            )

    # ⑦ STOP処理
    def _stop_phase(self) -> None:
        if self._stop_requested:
            self._stop_requested = False
            print("Alarm stop requested; alarms have been stopped.")
