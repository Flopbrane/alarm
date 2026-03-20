# -*- coding: utf-8 -*-
# pylint: disable=too-many-lines
"""アラームマネージャモジュール
alarm + now + actual_now → state
更新、次回鳴動日時更新、発火判定、鳴動制御
(アラームデータ管理・駆動指揮の役割)
[Manager Cycle]
start_cycle
   ↓
load_phase
   ↓
recalc_phase
   ↓
fire_phase
   ↓
save_phase
"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_manager_temp.py
#########################
# Future improvements:
# - 正規化系（_normalize_on_boot_and_edit）を別モジュール化候補
# - state 操作系の切り出し検討
from __future__ import annotations

# Standard library
from dataclasses import dataclass, field, replace
import inspect
import sys
import threading
import uuid
from datetime import datetime, time, timedelta
from pathlib import Path
from types import CodeType, FrameType
from typing import Any, Callable, Literal, TypedDict, Optional

# Local modules
# === mapper ===
from alarm_data_json_mapper import InternalToJsonMapper, JsonToInternalMapper
from alarm_ui_mapper import (
    InternaltoUIMapper,
    UIpatchtoInternalMapper,
    UItoInternalMapper,
)

# === model ===
from alarm_internal_model import AlarmInternal
from alarm_states_model import AlarmStateInternal
from alarm_json_model import AlarmJson, AlarmStateJson
from alarm_ui_model import AlarmListItem, AlarmUI, AlarmUIPatch

# === utils ===
from log_app import AppLogger

# === controller ===
from alarm_manager_cycle_control_options import (
    CONFIG_CHANGED,
    RUNNING,
    STARTUP,
    CycleOptions,
)

# === UI / GUI 関連 ===
from alarm_player import AlarmPlayer

# === core components ===
from alarm_repeat_datetime_checker import AlarmDatetimeChecker
from alarm_scheduler import AlarmScheduler
from alarm_storage import AlarmStorage
from constants import DEFAULT_SOUND
from env_paths import ALARM_PATH, BACKUP_DIR, DATA_DIR, STANDBY_PATH


class NextAlarmInfo(TypedDict): # UI表示用の次回鳴動予定アラーム情報
    """型ヒントの定義"""
    alarm: AlarmInternal
    next_datetime: datetime
    time_until: float

# ======================================================
# 🔹 RuntimeCache クラスの型定義関数
# =====================================================
def _new_next_fire_map() -> dict[str, datetime]:
    """次回鳴動予定日時のキャッシュを初期化するための関数"""
    return {}
def _new_fingerprint_map() -> dict[str, str]:
    """フィンガープリントのキャッシュを初期化するための関数"""
    return {}
def _new_event_queue() -> list[tuple[datetime, str]]:
    """イベントキューを初期化するための関数"""
    return []
def _new_just_created_id_list() -> list[str]:
    """新規作成されたIDリストを初期化するための関数"""
    return []

@dataclass
class RuntimeCache:
    """AlarmManager 内で再計算の結果をキャッシュするためのクラス"""
    # 🔹 Scheduler runtime cache "dict{alarm.id_str: state(alarm_id).next_fire_datetime}"
    next_fire_map: dict[str, datetime] = field(default_factory=_new_next_fire_map)
    # future scheduler optimization のためのキャッシュ（alarm_id → next_fire_datetime）
    event_queue: list[tuple[datetime, str]] = field(default_factory=_new_event_queue)
    # 🔹 Management cache"dict{alarm.id_str: fingerprint_value}"
    fingerprint_map: dict[str, str] = field(default_factory=_new_fingerprint_map)
    # 🔹 just created ids (stateが作られたばかりのidを保持して、次のサイクルで発火をスキップするためのリスト)
    just_created_ids: list[str] = field(default_factory=_new_just_created_id_list)


class AlarmManager:
    """アラーム設定を管理するクラス（STOP制御統一版）"""
    _MAX_BACKUPS = 3
    SnoozeResult = Literal["none", "expired", "limit", "toggle"]
    # "none": 何もしない
    # "expired": 時刻到達で解除（次を鳴らして良い）
    # "limit": 回数オーバー解除（強制終了）
    # "toggle": alarm dataのenabledを切り替える（有効→無効、無効→有効）
    CycleCondition = Literal["startup", "loop", "config_change"]
    # "startup": ソフト起動時
    # "loop": 通常ループ
    # "config_change": アラームデータの新規登録・編集・削除などの設定変更時

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
        alarm_path: Path = ALARM_PATH,
        standby_path: Path = STANDBY_PATH,
        logger: AppLogger | None = None,
        trace_id: str | None = None,
    ) -> None:
        # === paths ===
        self.base_dir: Path = self.get_base_dir()
        self.alarm_file_path: Path = alarm_path or ALARM_PATH
        self.standby_path: Path = standby_path or STANDBY_PATH
        self.backup_dir: Path = BACKUP_DIR
        self.data_dir: Path = DATA_DIR

        # === internal model ===
        self.alarms: list[AlarmInternal] = []
        self.states: list[AlarmStateInternal] = []
        self._states_map: dict[str, AlarmStateInternal] = {}
        # === settings ===
        self.snooze_default: int = 10
        self._stop_requested: bool = False

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
        self._last_stop_time: datetime | None = None
        # ソフト起動時刻（内部クロック基準）
        self._boot_datetime: datetime = self.internal_clock()
        # === clock jump detection ===
        self._last_tick: datetime | None = None
        # === irregular logger ===
        self.logger: AppLogger | None = logger
        # === trace_id ===
        self.trace_id: str | None = trace_id
        # === runtime_cache ===
        self.cache: RuntimeCache = RuntimeCache()
        # ====================================================
        # 🔹 State index
        # =====================================================
        self._states_map: dict[str, AlarmStateInternal] = {}
        # =====================================================
        # 🔹 UI listeners
        # =====================================================
        self._listeners: list[Callable[[], None]] = []
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

    def tick(self) -> datetime:
        """1ループ開始時に now を確定"""
        self._now = datetime.now().replace(microsecond=0)
        return self._now

    def internal_clock(self) -> datetime:
        """AlarmManager 内部で一貫して使用する現在時刻を返す"""
        if self._now is None:
            self.tick()
        assert self._now is not None  # ← 型チェッカーへの宣言
        return self._now
        # self._nowがNoneではない(=self._nowがセット済)場合、self._nowを返す。(1cycle,1tickの原則は崩れない)
        # self._nowがNoneの場合、self.tick()を呼び出して現在時刻をセットし、その後self._nowを返す。

    # ======================================================
    # 🔹 時計ジャンプ検出（スリープ復帰対策）
    # ======================================================
    def _detect_clock_jump(self, now: datetime) -> None:
        """PCスリープや時計変更による時間ジャンプを検出する"""

        if self._last_tick is None:
            self._last_tick = now
            return

        diff: float = (now - self._last_tick).total_seconds()

        # 2分以上飛んだらジャンプと判断
        if diff > 120:

            self.logger.warning(
                message="Clock jump detected",
                where=self.logger.where(),
                alarm_id=None,
                context={"jump_seconds": diff},
                timestamp=now,
)

            # 全アラーム再計算
            for state in self.states:
                if not state.lifecycle_finished:
                    state.needs_recalc = True

        self._last_tick = now

    # ======================================================
    # 🔹 AlarmStateInternal関係の更新処理
    # ======================================================
    def _recalc_states(self) -> None:
        """状態の正規化と next_fire_datetime 再計算（副作用なし）"""
        now: datetime = self.internal_clock()

        for alarm in self.alarms:
            state: AlarmStateInternal | None = self._get_state(alarm.id)

            # state が無ければ作る（初回・破損対応）
            if state is None:
                state = self._get_or_create_state(alarm.id)
                self.logger.warning(
                    message="State not found, created new state",
                    where=self._where(method_name="_recalc_states"),
                    alarm_id=alarm.id,
                    context={},
                    timestamp=now,
                )
                self.cache.just_created_ids.append(alarm.id)

            # 終了済みは触らない
            if state.lifecycle_finished:
                continue
            # 無効アラームは触らない
            if alarm.enabled is False:
                continue

            # 再計算が必要 or 未計算
            if state.needs_recalc or state.is_uncomputed:
                next_dt: datetime | None = self.scheduler.get_next_time(alarm, now)
                state.next_fire_datetime = next_dt
                state.needs_recalc = False
            elif state.next_fire_datetime is None or state.next_fire_datetime <= now:
                state.next_fire_datetime = self.scheduler.get_next_time(alarm, now)

    def _get_state(self, alarm_id: str) -> AlarmStateInternal | None:
        """alarm_id に対応する AlarmStateInternal を取得（存在しない場合は None）"""
        return self._states_map.get(alarm_id)

    def get_alarm_by_id(self, alarm_id: str) -> AlarmInternal | None:
        """alarm_id に対応する AlarmInternal を取得"""
        for alarm in self.alarms:
            if alarm.id == alarm_id:
                return alarm
        return None

    def get_state_by_id(self, alarm_id: str) -> AlarmStateInternal | None:
        """alarm_id に対応する AlarmStateInternal を取得"""
        return self._states_map.get(alarm_id)

    def get_alarm_list(self) -> list[AlarmListItem]:
        """CUI表示用管理アラーム一覧（UUIDを隠蔽）"""

        result: list[AlarmListItem] = []

        for alarm in self.alarms:

            state: AlarmStateInternal | None = self._states_map.get(alarm.id)

            result.append(AlarmListItem(
                alarm_id=alarm.id,          # 内部UUID
                alarm_ui=self.internal_to_ui_mapper.internal_to_ui(alarm), # AlarmUIモデル
                next_datetime=(
                    state.next_fire_datetime if state else None
                ),
            ))

        return result

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

        self.cache.next_fire_map = dict(sorted(pairs, key=lambda x: x[1]))

    def _handle_due_alarms(self) -> None:  # 実際に鳴らす処理
        """次回鳴動予定日時に達したアラームを処理する（自己修復型）"""

        now: datetime = self.internal_clock()

        for alarm_id in self.cache.next_fire_map:

            alarm: AlarmInternal | None = self.get_alarm_by_id(alarm_id)
            state: AlarmStateInternal | None = self.get_state_by_id(alarm_id)

            if state is None or state.lifecycle_finished:
                continue
            if alarm is None or not alarm.enabled:
                continue

            checker = AlarmDatetimeChecker(
                alarm=alarm,
                state=state,
                now=now,
                logger=self.logger
            )

            if checker.should_fire() and alarm_id not in self.cache.just_created_ids:
                self._fire_alarm(alarm, state)

    def _get_or_create_state(self, alarm_id: str) -> AlarmStateInternal:
        """alarm_id に対応する AlarmStateInternal を取得（存在しない場合は新規作成）"""
        state: AlarmStateInternal | None = self._states_map.get(alarm_id)

        if state is not None:
            return state

        new_state: AlarmStateInternal = AlarmStateInternal.initial(alarm_id)

        self.states.append(new_state)
        self._states_map[alarm_id] = new_state

        self.cache.just_created_ids.append(alarm_id)

        return new_state

    def _fire_alarm(self, alarm: AlarmInternal, state: AlarmStateInternal) -> None:
        """アラームを発火させる"""

        self.player.play(str(alarm.sound), duration=alarm.duration)

        now: datetime = self.internal_clock()

        state.triggered_at = now
        state.last_fired_at = now

        if alarm.repeat == "single":
            state.lifecycle_finished = True
            state.next_fire_datetime = None
            state.needs_recalc = False

        elif alarm.enabled:
            next_fire_dt: datetime | None = self.scheduler.get_next_time(alarm, now)

            if next_fire_dt is None:
                state.lifecycle_finished = True
                state.next_fire_datetime = None

                self.logger.error(
                    message="Failed to calculate next fire datetime",
                    where=self._where(method_name="_fire_alarm"),
                    alarm_id=alarm.id,
                    context={
                        "state_id": state.id,
                        "repeat": alarm.repeat,
                        "now": now,
                    },
                    timestamp=now,
                )

            else:
                state.next_fire_datetime = next_fire_dt
                state.needs_recalc = False
    # ======================================================

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
                state.next_fire_datetime = None
                state.needs_recalc = True

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

    def get_next_alarms(self, count: int = 5) -> list[NextAlarmInfo]:
        """
        次回鳴動予定アラームを最大 count 件返す（★UI表示専用★）
        発火ロジックには影響しない
        """
        now: datetime = self.internal_clock()

        self._update_next_fire_runtime()

        results: list[NextAlarmInfo] = []

        for alarm_id, next_dt in self.cache.next_fire_map.items():
            alarm: AlarmInternal | None = self.get_alarm_by_id(alarm_id)
            if alarm is None:
                continue

            # 無効アラームは表示しない
            if not alarm.enabled:
                continue

            results.append(
                {
                    "alarm": alarm,
                    "next_datetime": next_dt,
                    "time_until": (next_dt - now).total_seconds(),
                }
            )

            if len(results) >= count:
                break

        return results
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
                if state.id not in self.cache.just_created_ids:
                    targets.append(state)

        # 共通処理
        for state in targets:
            self._reset_state_for_future(state)

        print(f"target_list: {[s.id for s in targets]}")
        print(f"_just_created_id_list: {self.cache.just_created_ids}")

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
    # ======================================================
    # ======================================================
    # 🔹 UIからの編集リクエストを全て受け取る入口
    # ======================================================
    # ======================================================
    def apply_alarm_mutation(
        self,
        action: Literal["add", "update", "delete", "toggle"],
        payload: Any,
    ) -> None:
        """★編集処理の入口は apply_alarm_mutation だけ★"""

        # =========================================
        # ① mutation
        # =========================================
        if action == "add":
            alarm: AlarmInternal | None = self._add_alarm(payload)
            if alarm:
                self.cache.just_created_ids.append(alarm.id)

        elif action == "update":
            alarm_id: str
            patch: AlarmUIPatch
            alarm_id, patch = payload

            existing: AlarmInternal | None = self.get_alarm_by_id(alarm_id)
            if existing is not None:
                base_ui: AlarmUI = self.internal_to_ui_mapper.internal_to_ui(existing)
                merged_ui: AlarmUI = self._merge_ui(base_ui, patch)
                updated: AlarmInternal | None = self._update_alarm(alarm_id, merged_ui)
                if updated:
                    self.cache.just_created_ids.append(alarm_id)

        elif action == "delete":
            self._delete_alarms(payload)

        elif action == "toggle":
            self._toggle_alarm(payload)
            self.cache.just_created_ids.append(payload)

        else:
            raise ValueError(action)

        # =========================================
        # ② normalize
        # =========================================
        self._normalize_on_boot_and_edit(reason="edit")

        # =========================================
        # ③ state再計算（重要）
        # =========================================
        self._recalc_phase()

        # =========================================
        # ④ cache再構築（🔥追加ポイント）
        # =========================================
        self._rebuild_runtime_cache()

        # =========================================
        # ⑤ save
        # =========================================
        self._save_phase()

    # ======================================================
    # 🔹 アラームデータから識別情報を得る
    # ======================================================
    def _build_alarm_fingerprint(self, alarm: AlarmInternal) -> str:
        """アラームの識別情報を構築する（重複検出などに使用）
        AlarmInternal の "repeat|datetime_|weekday|interval_days|interval_weeks" 
        を組み合わせて文字列を生成する   
        """
        parts: list[str] = []

        # repeat
        parts.append(f"repeat={alarm.repeat}")

        # datetime 正規化
        dt: datetime | time | None = alarm.datetime_

        if isinstance(dt, datetime):
            parts.append(f"dt={dt.strftime("%Y-%m-%d %H:%M")}")
        elif isinstance(dt, time):
            parts.append(f"dt={dt.strftime("%H:%M")}")
        # dt が None の場合は何もしない

        # weekday
        if alarm.weekday:
            parts.append(f"weekday={','.join(map(str, sorted(alarm.weekday)))}")

        # interval
        if alarm.interval_days is not None:
            parts.append(f"d={alarm.interval_days}")
        # interval_weeks は None と 0 を区別して扱う（0は毎日、Noneは非反復）
        # if alarm.interval_weeks not in (None, 1): でも同じ結果になる
        if alarm.interval_weeks and alarm.interval_weeks != 1:
            parts.append(f"w={alarm.interval_weeks}")
        # enabled
        if alarm.enabled is True:
            parts.append("enabled")
        else:
            parts.append("disabled")

        return "|".join(parts)

    def _is_duplicate_except(
        self,
        alarm: AlarmInternal,
        ignore_id: str,
    ) -> bool:
        """ignore_id を除いて、同じフィンガープリントのアラームが存在するかどうかをチェックする"""
        new_fp: str = self._build_alarm_fingerprint(alarm)

        for aid, fp in self.cache.fingerprint_map.items():
            if aid == ignore_id:
                continue
            if fp == new_fp:
                return True

        return False
    # ========================編集ブロック==============================

    # =====================================================
    # 🔹 UUIDの発行メソッド
    # =====================================================
    def get_next_id(self) -> str:
        """次のアラームIDを取得"""
        return str(uuid.uuid4())

    # ======================================================
    # 🔹 RuntimeCacheの再構築
    # ======================================================
    def _rebuild_runtime_cache(self) -> None:
        """
        RuntimeCacheを完全再構築する

        Source of Truth:
            alarms
            states

        RuntimeCacheは派生データなので
        壊れてもこの関数で再生成できる。
        """
        cache: RuntimeCache = self.cache

        cache.next_fire_map.clear()
        cache.event_queue.clear()
        cache.fingerprint_map.clear()

        for alarm in self.alarms:
            # fingerprint_mapの再構築（ID → フィンガープリント）
            cache.fingerprint_map[alarm.id] = self._build_alarm_fingerprint(alarm)

            # _state_mapの再構築(無効アラームは除外)
            if not alarm.enabled:
                continue
            state: AlarmStateInternal | None = self._states_map.get(alarm.id)

            # next_fire_mapの再構築（ID → 次回鳴動予定日時）
            if state is None:
                continue
            if state.lifecycle_finished:
                continue
            next_dt: datetime | None = state.next_fire_datetime
            if next_dt is not None:
                cache.next_fire_map[alarm.id] = next_dt

    # ======================================================
    # 🔹 新規データの追加
    # ======================================================
    def _add_alarm(self, ui_alarm: AlarmUI) -> AlarmInternal:

        internal: AlarmInternal = self.ui_to_internal_mapper.ui_to_internal(ui_alarm)

        if self._is_duplicate_except(internal, ignore_id=""):
            raise ValueError("Duplicate alarm")

        alarm_id: str = self.get_next_id()
        internal.id = alarm_id

        self.alarms.append(internal)

        # stateはここでOK（理由あとで説明）
        self._get_or_create_state(alarm_id)

        return internal

    # ======================================================
    # 🔹 既存アラームの編集関数
    # ======================================================
    def _update_alarm(self, alarm_id: str, ui_alarm: AlarmUI) -> AlarmInternal:

        internal: AlarmInternal | None = self.get_alarm_by_id(alarm_id)
        if internal is None:
            raise ValueError("Alarm not found")

        updated: AlarmInternal = self.ui_to_internal_mapper.ui_to_internal(ui_alarm)
        updated.id = alarm_id

        if self._is_duplicate_except(updated, alarm_id):
            raise ValueError("Duplicate alarm")

        self._replace_alarm(updated)

        # 🔥 ここ追加（超重要）
        self._replace_alarm(updated)
        self._ensure_state_exists(alarm_id)
        self._adjust_state_after_update(alarm_id)

        return updated

    def _replace_alarm(self, new_internal: AlarmInternal) -> None:
        """既存アラームを更新"""
        for idx, a in enumerate(self.alarms):
            if a.id == new_internal.id:
                self.alarms[idx] = new_internal
                return

        # 見つからなければ追加
        self.alarms.append(new_internal)

    def _ensure_state_exists(self, alarm_id: str) -> None:
        """stateが存在しなければ作る"""
        for s in self.states:
            if s.id == alarm_id:
                return
        self._get_or_create_state(alarm_id)
    # ======================================================
    # 🔹 フィンガープリント重複チェック
    def _exists_duplicate_fingerprint(self, fingerprint: str, ignore_id: str | None = None) -> bool:
        """同じフィンガープリントのアラームが存在するかどうかをチェックする"""
        for alarm_id, fp in self.cache.fingerprint_map.items():
            if alarm_id == ignore_id:
                continue
            if fp == fingerprint:
                return True
        return False
    # ======================================================
    # 🔹 alarmとstateの整合性チェック
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
    # ======================================================
    # 🔹 AlarmUIからの編集マージ関数
    def _merge_ui(self, base: AlarmUI, patch: AlarmUIPatch) -> AlarmUI:
        merged: AlarmUI = base

        for field_name, value in vars(patch).items():
            if field_name == "id":
                continue
            if value is not None:
                merged = replace(
                    merged, **{field_name: value}
                )  # dataclassのreplaceを使用してフィールドを更新

        return merged

    # ======================================================
    # 🔹 アラームの有効/無効切り替え
    # ======================================================
    def _toggle_alarm(self, alarm_id: str) -> None:
        for a in self.alarms:
            if a.id == alarm_id:
                a.enabled = not a.enabled
                return

    # ======================================================
    # 🔹 アラーム削除
    # ======================================================
    # GUI一覧表から、複数のアラームデータを削除する
    def _delete_alarms(self, ids: list[str]) -> None:
        """GUI複数削除"""
        self._remove_alarms_by_ids(set(ids))

    def _remove_alarms_by_ids(self, ids: set[str]) -> None:

        self.alarms = [a for a in self.alarms if a.id not in ids]
        self.states = [s for s in self.states if s.id not in ids]

        self._states_map = {s.id: s for s in self.states}
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
                except (RuntimeError, ValueError, TypeError, AttributeError) as e:
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
        """GUI通知:notify_listeners で呼び出す関数を登録する"""
        if func not in self._listeners:
            self._listeners.append(func)

    def remove_listener(self, func: Callable[[], None]) -> None:
        """GUI通知:notify_listeners で呼び出す関数を削除する"""
        if func in self._listeners:
            self._listeners.remove(func)

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

        self.save()
        self.save_standby()

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
    # アラーム鳴動停止
    # ======================================================
    def request_stop(self) -> None:
        """アラーム停止要求"""
        self._stop_requested = True

    def stop_alarm(self, state: AlarmStateInternal) -> None:
        """アラーム停止 → スヌーズ情報クリア"""
        state.snoozed_until = None
        state.snooze_count = 0
        state.triggered = False
        state.triggered_at = None

        # 多重発火防止：直後に再発火しないよう数秒 ahead にしておく
        state.last_fired_at = (self.internal_clock()) + timedelta(seconds=10)

        self.save()
        self.request_stop()
        self.save_standby()

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

        self.states.clear()  # 先にクリアしておく（破損対応）

        json_states: list[AlarmStateJson] = self.storage.load_standby()
        if not json_states:
            return []

        # JSON → internal
        for s in json_states:
            state: AlarmStateInternal = self.json_to_internal_mapper.alarm_state_json_to_internal(s)
            self.states.append(state)

        # state不足補完
        existing_ids: set[str] = {s.id for s in self.states}

        for alarm in self.alarms:
            if alarm.id not in existing_ids:

                new_state: AlarmStateInternal = AlarmStateInternal.initial(alarm.id)

                self.states.append(new_state)

                self.logger.info(
                    message="State auto-created",
                    where=self._where(method_name="load_standby"),
                    alarm_id=alarm.id,
                )

        # ⭐ index rebuild
        self._rebuild_state_map()

        return self.states

    def _rebuild_state_map(self) -> None:
        """state list から state_map を再構築"""
        self._states_map: dict[str, AlarmStateInternal] = {state.id: state for state in self.states}

    # -----------------------------------------
    # 🔹 alarms.json , standby.json
    # -----------------------------------------
    def load_all(self) -> None:
        """alarms.json と standby.json を両方読み込んで整合性を保つ"""
        self.load_alarms()
        self.load_standby()

        # 🔹 1. 旧ID検出
        old_ids: set[object] = {a.id for a in self.alarms}

        # 🔹 2. UUID変換が必要か判定
        def needs_migration(id_: object) -> bool:
            if isinstance(id_, int):
                return True
            if isinstance(id_, str):
                return len(id_) < 32
            return True

        target_ids: set[object] = {i for i in old_ids if needs_migration(i)}

        if not target_ids:
            # 何もしない(state取得は関数にまとめているので、ここで整合性は取れる)
            self._ensure_state_id_integrity()
            return

        # 🔹 4. alarms更新
        for alarm in self.alarms:
            if needs_migration(alarm.id):
                old_id: str = alarm.id
                new_id = str(uuid.uuid4())
                state: AlarmStateInternal | None = self._get_state(old_id)

                if state:
                    state.id = new_id

                alarm.id = new_id

        # 🔹 6. 整合性修復
        self._ensure_state_id_integrity()

        # 🔹 7. 保存
        self.save()
        self.save_standby()

    # ======================================================
    # 保存
    # ======================================================
    def save(self) -> None:
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
            result
            for a in normalized
            if (result := self.internal_to_json_mapper.alarm_internal_to_json(a)) is not None
            ]

        self.storage.save_alarms(json_alarms)

    def save_standby(self) -> None:
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

    def get_sleep_seconds(self) -> float:
        """次のアラームまでの秒数を返す（CUI表示用）"""
        next_alarms: list[NextAlarmInfo] = self.get_next_alarms(1)

        if not next_alarms:
            return 30  # アラーム無し

        next_alarm: NextAlarmInfo = next_alarms[0]

        seconds: float = next_alarm["time_until"]

        return max(1, min(seconds, 60))
    # ======================================================
    # ======================================================
    # 🔹 サイクル開始の入り口（公開API）
    # ======================================================
    # ======================================================
    def start_cycle(self, condition: CycleCondition) -> None:
        """サイクル開始の入り口（公開API）"""

        self.cache.just_created_ids.clear()

        options_map: dict[str, CycleOptions] = {
            "startup": STARTUP, # 起動時は完全サイクル（load → recalc → fire → save → notify）
            "loop": RUNNING, # メインループ（recalc → fire → save → notify）
            "config_change": CONFIG_CHANGED, # 設定変更時（recalc → fire → save → notify）
        }

        opt: CycleOptions | None = options_map.get(condition)
        if opt is None:
            raise ValueError(f"Unknown cycle condition: {condition}")

        self._run_cycle(opt)

    # ======================================================
    # 🔹 manager駆動の入り口
    # ======================================================
    def _run_cycle(self, opt: CycleOptions) -> None:
        """AlarmManager の1サイクル処理（内部エンジン）"""

        # ==================================================
        # ① 内部クロック確定（1 cycle = 1 now）
        # ==================================================
        self._begin_cycle()
        # ★ここ追加
        now: datetime = self._now # type: ignore
        self._detect_clock_jump(now)
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

    # ① cycle開始の入り口（内部クロック確定）
    def _begin_cycle(self) -> datetime:
        self.tick()
        return self._now # type: ignore

    # ② loadフェーズ
    def _load_phase(self) -> None:
        self.load_all()

    # ③ 再計算フェーズ（超重要）
    def _recalc_phase(self) -> None:
        self._repair_invalid_states()
        self._recalc_states()
        self._update_next_fire_runtime()
        # ★ここ
        self._rebuild_runtime_cache()

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
            self.save_standby()
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
            self.save()
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
