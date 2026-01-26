# -*- coding: utf-8 -*-
# pylint: disable=C0302
"""
AlarmManager - AlarmInternal/dataclass完全対応版
・辞書アクセス完全排除
・standby整合性修正
・STOP後の多重発火防止改善
・get_current_alarmロジック修正
・print_next_alarms の完全dataclass対応
"""
# 標準モジュール
import sys
import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, List, Optional, TypedDict, cast

# サードパーティー
import pygame

# 自作モジュール
from alarm_data_json_mapper import InternalToJsonMapper, JsonToInternalMapper  # 旧Loader
from alarm_internal_model import AlarmInternal, AlarmStateInternal
from alarm_json_model import AlarmJson, AlarmStateJson
from alarm_player import AlarmPlayer
from alarm_repeat_datetime_checker import AlarmDatetimeChecker
from alarm_scheduler import AlarmScheduler
from alarm_storage import AlarmStorage
from alarm_ui_mapper import InternaltoUIMapper, UItoInternalMapper
from alarm_ui_model import AlarmStateView, AlarmUI
from constants import DEFAULT_SOUND
from env_paths import ALARM_PATH, BACKUP_DIR, DATA_DIR, STANDBY_PATH


class NextAlarmInfo(TypedDict):
    """型ヒントの定義"""

    alarm: AlarmInternal
    next_datetime: datetime
    time_until: float


class AlarmManager:
    """アラーム設定を管理するクラス（STOP制御統一版）"""

    _MAX_BACKUPS = 3

    @staticmethod
    def get_base_dir() -> Path:
        """PyInstaller or Python 実行フォルダ"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    # ======================================================
    # 初期化
    # ======================================================
    def __init__(self) -> None:
        # 基準Pathセットアップ
        self.base_dir: Path = self.get_base_dir()
        self.backup_dir: Path = BACKUP_DIR
        self.data_dir: Path = DATA_DIR
        self.alarm_file_path: Path = ALARM_PATH
        self.standby_file_path: Path = STANDBY_PATH
        # dataclass コンストラクタ
        self.alarms: list[AlarmInternal] = []
        self.alarm: AlarmInternal | None = None
        self.states: list[AlarmStateInternal] = []
        self.state: AlarmStateInternal | None = None
        # データ保存・読み込み用
        self.storage = AlarmStorage()
        # 時刻計算用
        self._now: datetime | None = None
        self.scheduler = AlarmScheduler()
        self.datetime_checker: AlarmDatetimeChecker = AlarmDatetimeChecker(
            state=AlarmStateInternal(id=""))
        # データ変換用
        # UI ↔ Internal
        self.ui_to_internal_mapper = UItoInternalMapper()
        # Internal -> UI
        self.internal_to_ui_mapper = InternaltoUIMapper()

        # Json ↔ Internal
        self.json_to_internal_mapper = JsonToInternalMapper()
        self.internal_to_json_mapper = InternalToJsonMapper()

        # 起動日時記録
        self._boot_time: datetime = datetime.now()
        # アラーム再生用
        self.player = AlarmPlayer()
        self.snooze_default = 5
        self._stop_requested = False
        self._stop_block_seconds = 5
        self._last_stop_time: Optional[datetime] = None
        self.currently_playing: Optional[str] = None
        self.alarm_playing = False

        self._stop_event = threading.Event()
        self._watch_thread: Optional[threading.Thread] = None

        # try:
        #     self.alarms = []
        # except (FileNotFoundError, json.JSONDecodeError) as e:
        #     print(f"[エラー] 読み込み失敗 → 新規起動: {e}")
        #     self.alarms = []
        #     self.states = []

        self._listeners: List[Callable[[], None]] = []

        try:
            pygame.mixer.init()
            self.default_sound: Path | None = Path(DEFAULT_SOUND)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # pygame は環境依存で例外型が不定なため Exception を許容する
            print(f"[注意] pygame初期化失敗: {e}")
            self.default_sound = None

    # ======================================================
    # 計算軸になる、ソフト内の基準時刻設定
    # ======================================================
    def tick(self) -> None:
        """1ループ開始時に一度だけ now を確定"""
        self._now = datetime.now().replace(microsecond=0)


    def internal_clock(self) -> datetime:
        """ソフト駆動基準の現在基準時刻を返す"""
        if self._now is None:
            self.tick()

        assert self._now is not None  # ← 型チェッカーへの宣言
        return self._now

    # ---------------------------------------------------
    # CUIの駆動、アラーム監視
    # ---------------------------------------------------
    def run(self) -> None:
        """アラーム監視ループ"""
        self._stop_event.clear()  # 再起動時に備える
        while not self._stop_event.is_set():
            self._check_and_fire()
            time.sleep(1)

    def _fire_alarm(
        self,
        alarm: AlarmInternal,
        state: Optional[AlarmStateInternal] = None,
        ) -> None:
        self.player.play(
            sound=str(alarm.sound),
            duration=alarm.duration,
            )

        # 🔽 ここからは Manager の仕事
        # Update the alarm instance directly (self.state may be None)
        now: datetime = datetime.now()
        if state is not None:
            state.triggered = True
            state.triggered_at = now
            state.last_fired_at = now

        self._save_standby()

    def driving_stop(self) -> None:
        """監視停止要求を出す（スレッド/ループ終了用）"""
        self._stop_event.set()
        self.player.stop()  # ← 音も止めたいなら追加

    # ======================================================
    # STOP
    # ======================================================
    def request_stop(self) -> None:
        """アラーム停止要求"""
        self._stop_requested = True
        self._last_stop_time = datetime.now()

    def stop_alarm(self, state: AlarmStateInternal) -> None:
        """アラーム停止 → スヌーズ情報クリア"""
        state.snoozed_until = None
        state.snooze_count = 0
        state.triggered = False
        state.triggered_at = None

        # 多重発火防止：直後に再発火しないよう数秒 ahead にしておく
        state.last_fired_at = datetime.now() + timedelta(seconds=10)

        self._save()
        self.request_stop()
        self._save_standby()

    # ======================================================
    # 現在のアラーム判定
    # ======================================================
    def get_current_alarm(self) -> Optional[AlarmStateInternal]:
        """スヌーズ中 or 直前に鳴ったアラームを返す"""

        # 1. スヌーズ中のアラーム（最優先）
        for state in self.states:
            if state.snoozed_until:
                return state

        # 2. triggered_at があるアラームを抽出
        fired: List[AlarmStateInternal] = [
            a for a in self.states if a.triggered and a.triggered_at
        ]

        if not fired:
            return None

        # Pylance対策：keyは常に datetime を返す
        return max(fired, key=lambda a: a.triggered_at or datetime.min)

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

    def _adjust_state_after_update(self, alarm_id: int) -> None:
        """アラーム編集後に state を安全な状態へ調整する"""

        state: AlarmStateInternal | None = self.get_state_by_id(alarm_id)
        if state is None:
            # state が無ければ新規作成（安全側）
            self.states.append(AlarmStateInternal.initial(alarm_id))
            return

        # --- 編集後は状態をリセット ---
        state.snoozed_until = None
        state.snooze_count = 0
        state.triggered = False
        state.triggered_at = None
        # last_fired_at は保持（ログとして有用）

    def get_state_by_id(self, alarm_id: int) -> AlarmStateInternal | None:
        """IDで state を取得"""
        for s in self.states:
            if s.id == alarm_id:
                return s
        return None

    def update_alarm(self, ui_alarm: AlarmUI) -> bool:
        """アラーム編集"""
        if ui_alarm.id is None:
            return False

        # 1. 既存 alarm を取得
        alarm: AlarmInternal | None = self.get_alarm_by_id(ui_alarm.id)
        if alarm is None:
            return False

        # 2. 既存 alarm → UI に変換（編集前のベース）
        base_ui: AlarmUI = self.internal_to_ui_mapper.internal_to_ui(alarm)

        # 3. UI の上書き（変更された部分だけ）
        merged_ui: AlarmUI = self._merge_ui(base_ui, ui_alarm)

        # 4. UI → Internal 変換
        new_internal: AlarmInternal = self.ui_to_internal_mapper.ui_to_internal(merged_ui)
        new_internal.id = alarm.id

        # 5. alarm を置き換え
        self._replace_alarm(new_internal)

        # 6. 必要なら state を初期化 or 調整
        self._adjust_state_after_update(alarm.id)

        self._save()
        self._notify_listeners()
        return True

    def _merge_ui(self, base_ui: AlarmUI, patch_ui: AlarmUI) -> AlarmUI:
        """
        base_ui に patch_ui の「入力がある項目だけ」を上書きして返す。
        空文字/None/空リストは「未入力」とみなして上書きしない。
        """

        def use_patch_str(v: str) -> bool:
            return bool(v and v.strip())

        def use_patch_list(v: list[Any] | None) -> bool:
            return v is not None and len(v) > 0

        # dataclasses.replace で安全に生成（base_uiは壊さない）
        merged: AlarmUI = base_ui

        # id（基本は base を使う）
        if patch_ui.id is not None:
            merged = replace(merged, id=patch_ui.id)

        # 文字列系
        if use_patch_str(patch_ui.name):
            merged = replace(merged, name=patch_ui.name)
        if use_patch_str(patch_ui.date):
            merged = replace(merged, date=patch_ui.date)
        if use_patch_str(patch_ui.time):
            merged = replace(merged, time=patch_ui.time)
        if use_patch_str(patch_ui.repeat):
            merged = replace(merged, repeat=patch_ui.repeat)
        if use_patch_str(patch_ui.custom_desc):
            merged = replace(merged, custom_desc=patch_ui.custom_desc)
        if use_patch_str(patch_ui.sound):
            merged = replace(merged, sound=patch_ui.sound)

        # リスト系
        if use_patch_list(patch_ui.weekday):
            merged = replace(merged, weekday=cast(List[Any], patch_ui.weekday))
        if use_patch_list(patch_ui.week_of_month):
            merged = replace(merged, week_of_month=patch_ui.week_of_month)

        # 数値・bool系：ここは「上書き条件」を決める必要がある
        # 例：interval_weeks は 0 を無効として扱うなら >0 のときだけ
        if patch_ui.interval_weeks and patch_ui.interval_weeks > 0:
            merged = replace(merged, interval_weeks=patch_ui.interval_weeks)

        # bool は「False も有効入力」なので、常に上書きしたい…が、
        # patch_ui の生成側で「変更したかどうか」が分からないと危険。
        # ここでは "常に上書き" にせず、方針を決めた方が安全です。
        # いったん保留にするなら、enabled/skip_holiday は別メソッドで更新がおすすめ。

        # duration / snooze_minutes / snooze_repeat_limit も「0 を有効にするか」で条件が変わる
        # 例：>0 のときだけ上書き
        if patch_ui.duration and patch_ui.duration > 0:
            merged = replace(merged, duration=patch_ui.duration)
        if patch_ui.snooze_minutes and patch_ui.snooze_minutes > 0:
            merged = replace(merged, snooze_minutes=patch_ui.snooze_minutes)
        if patch_ui.snooze_repeat_limit and patch_ui.snooze_repeat_limit > 0:
            merged = replace(merged, snooze_repeat_limit=patch_ui.snooze_repeat_limit)

        return merged

    # =====================================================
    # 🔹 アラームデータ正規化・変換ユーティリティ（頻度高）
    # =====================================================
    def get_next_id(self) -> int:
        """次のアラームIDを取得"""
        if not self.alarms:
            return 1
        return max(a.id for a in self.alarms) + 1

    # ======================================================
    # 新規データ・編集データの追加
    # ======================================================
    def add_alarm(self, ui_alarm: AlarmUI) -> Optional[AlarmInternal]:
        """新規アラームを追加する"""

        # 1. ID を決定（Manager の責務）
        alarm_id: int = self.get_next_id()

        # 2. UI → Internal 変換
        try:
            internal: AlarmInternal = self.ui_to_internal_mapper.ui_to_internal(ui_alarm)
        except (ValueError, TypeError) as e:
            print(f"[エラー] アラーム変換失敗: {e}")
            # ここで失敗したら「登録できなかった」と明示的に返す
            return None

        # 3. ID を正式に付与
        internal.id = alarm_id

        # 4. alarms に登録
        self.alarms.append(internal)

        # 5. state を初期状態で生成（必ず id を揃える）
        state: AlarmStateInternal = AlarmStateInternal.initial(alarm_id)
        self.states.append(state)

        # 6. 永続化・通知
        self._save()
        self._notify_listeners()

        return internal

    def _replace_alarm(self, new_internal: AlarmInternal) -> None:
        """内部リストのアラームを置換または追加し、対応する state を保証する"""
        # 既存アラームを置換
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
        self.states.append(AlarmStateInternal.initial(new_internal.id))
    # ======================================================
    # 🔹 InternalモデルからViewモデルへの変換ユーティリティ
    # ======================================================
    def build_state_view(self, state: AlarmStateInternal) -> AlarmStateView:
        """AlarmStateInternal → AlarmStateView"""
        return AlarmStateView(
            id=state.id,
            snoozed_until=state.snoozed_until.isoformat() if state.snoozed_until else None,
            snooze_count=state.snooze_count,
            triggered=state.triggered,
            triggered_at=state.triggered_at.isoformat() if state.triggered_at else None,
            last_fired_at=state.last_fired_at.isoformat() if state.last_fired_at else None,
        )

    # ======================================================
    # スヌーズ解除判定
    # ======================================================
    def _check_snooze(self, alarm: AlarmInternal, state: AlarmStateInternal, now: datetime) -> bool:
        """スヌーズ解除判定"""
        su: datetime | None = state.snoozed_until
        if su is None:
            return False

        # snooze_limit is stored on the AlarmInternal; prefer the alarm resolved by id if available.
        stored_alarm: AlarmInternal | None = self.get_alarm_by_id(state.id)
        target_alarm: AlarmInternal = stored_alarm if stored_alarm is not None else alarm
        snooze_limit: Any | int = getattr(target_alarm, "snooze_limit", self.snooze_default)

        if state.snooze_count >= snooze_limit:
            state.snoozed_until = None
            state.snooze_count = 0
            state.triggered = False
            return False

        if now >= su.replace(second=0, microsecond=0):
            state.snoozed_until = None
            return True

        return False

    # ======================================================
    # 発火確定
    # ======================================================
    def _mark_triggered(self,
                    alarm:AlarmInternal,
                    state: AlarmStateInternal,
                    now: datetime
                    ) -> bool:
        """アラーム発火確定"""
        if not alarm.enabled:
            return False

        last_fire: datetime | None = state.last_fired_at
        if last_fire and (now - last_fire).total_seconds() < 5:
            return False

        state.snoozed_until = None
        state.snooze_count = 0
        state.triggered = True
        state.triggered_at = now
        state.last_fired_at = now
        state.triggered = True

        self._save()
        self._save_standby()
        self._notify_listeners()

        return True

    # ======================================================
    # 🔹 鳴らすべきかどうか判断する
    # ======================================================
    def _check_and_fire(self) -> None:
        due_alarms: List[AlarmInternal] = self.scheduler.find_due_alarms(self.alarms)
        for alarm in due_alarms:
            self._fire_alarm(alarm)

    # -----------------------------------------
    # 🔹 alarms.json のみ読み込む
    # -----------------------------------------
    def load_alarms(self) -> List[AlarmInternal]:
        """alarms.json を読み込み、self.alarms に反映する"""
        json_alarms: List[AlarmJson] = self.storage.load_alarms()
        if not json_alarms:
            self.alarms = []
            return self.alarms

        self.alarms = [self.json_to_internal_mapper.alarm_json_to_internal(a) for a in json_alarms]
        return self.alarms

    # -----------------------------------------
    # 🔹 standby.json のみ読み込む
    # -----------------------------------------
    def load_standby(self) -> None | List[AlarmStateInternal]:
        """standby.json だけ読み込んで self.alarms の内部状態に反映する"""
        json_states: List[AlarmStateJson] = self.storage.load_standby()
        if not json_states:
            return None

        # Convert standby JSON entries to internal state dataclasses
        self.states = [
            self.json_to_internal_mapper.alarm_state_json_to_internal(s) for s in json_states
            ]

        # Ensure there's a state entry for every registered alarm
        existing_ids: set[int] = {s.id for s in self.states}
        for alarm in self.alarms:
            if alarm.id not in existing_ids:
                self.states.append(AlarmStateInternal.initial(alarm.id))

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
        existing_ids: set[int] = {s.id for s in self.states}
        for alarm in self.alarms:
            if alarm.id not in existing_ids:
                self.states.append(AlarmStateInternal.initial(alarm.id))

        # Persist standby to ensure consistency on disk
        self._save_standby()
    # ======================================================
    # 保存
    # ======================================================
    def _save(self) -> None:
        json_alarms: list[AlarmJson] = [
            self.internal_to_json_mapper.alarm_internal_to_json(a) for a in self.alarms
        ]
        self.storage.save_alarms(json_alarms)

    # def _save_alarms(self, alarms: List[AlarmInternal]) -> None:
    #     j_alarms: List[dict[str, Any]] = [asdict(a) for a in alarms]
    #     self.storage.save_alarms(j_alarms)

    def _save_standby(self, states: Optional[list[AlarmStateInternal]] = None) -> None:
        actual_states: List[AlarmStateInternal] = states if states is not None else self.states

        json_states: list[AlarmStateJson] = [
            self.internal_to_json_mapper.alarm_state_internal_to_json(s)
            for s in actual_states
        ]

        self.storage.save_standby(json_states)

    # ======================================================
    # アラーム削除
    # ======================================================
    # GUI一覧表から、アラームデータを削除する
    def remove_alarm(self, alarm_id: int) -> None:
        """アラーム削除"""
        self._remove_alarms_by_ids({alarm_id})

    # GUI一覧表から、複数のアラームデータを削除する
    def delete_alarms(self, ids: List[int]) -> None:
        """GUI複数削除"""
        self._remove_alarms_by_ids(set(ids))

    # 内部制御
    def _remove_alarms_by_ids(self, ids: set[int]) -> None:
        """内部専用：ID集合でアラームを削除"""
        self.alarms = [a for a in self.alarms if a.id not in ids]
        self.states = [s for s in self.states if s.id not in ids]
        self._save()
        self._save_standby()
        self._notify_listeners()

    # ======================================================
    # ON/OFF
    # ======================================================
    def toggle_alarm(self, alarm_id: int) -> None:
        """アラーム ON/OFF"""
        for a in self.alarms:
            if a.id == alarm_id:
                a.enabled = not a.enabled
                break
        self._save()
        self._notify_listeners()

    # ======================================================
    # スヌーズ
    # ======================================================
    def snooze_alarm(
        self,
        alarm: AlarmInternal,
        state:AlarmStateInternal,
        minutes: int | None = None
        ) -> None:
        """アラームをスヌーズ"""
        now: datetime = datetime.now()
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
    # 次のアラーム
    # ======================================================
    def get_next_alarms(self, count: int = 5) -> list[NextAlarmInfo]:
        """直近の該当アラームを5件返す"""
        now: datetime = datetime.now()
        upcoming: list[tuple[AlarmInternal, datetime]] = []

        for alarm in self.alarms:
            if not alarm.enabled:
                continue

            next_dt: datetime | None = self.scheduler.get_next_time(alarm, now)
            if not next_dt:
                continue
            if next_dt <= now:
                continue

            upcoming.append((alarm, next_dt))

        upcoming.sort(key=lambda x: (x[1] - now).total_seconds())

        result: list[NextAlarmInfo] = []
        for alarm, next_dt in upcoming[:count]:
            result.append(
                {
                    "alarm": alarm,
                    "next_datetime": next_dt,
                    "time_until": (next_dt - now).total_seconds(),
                }
            )
        return result

    def get_next_alarm(self) -> tuple[AlarmInternal, datetime] | None:
        """直近の該当アラームを1件返す"""
        r: List[NextAlarmInfo] = self.get_next_alarms(1)

        if not r:
            return None

        info: NextAlarmInfo = r[0]
        return info["alarm"], info["next_datetime"]

    def get_alarm_settings(self) -> list[tuple[AlarmInternal, datetime | None]]:
        """登録アラームと次回時刻を返す（表示しない）"""
        result: list[Any]
        result = []
        now: datetime = datetime.now()

        for alarm in self.alarms:
            next_time: datetime | None = self.scheduler.get_next_time(alarm, now)
            result.append((alarm, next_time))

        return result

    # ======================================================
    # ID検索
    # ======================================================
    def get_alarm_by_id(self, alarm_id: int) -> AlarmInternal | None:
        """ID検索"""
        for a in self.alarms:
            if a.id == alarm_id:
                return a
        return None

    # ======================================================
    # GUI通知
    # ======================================================
    def _notify_listeners(self) -> None:
        """GUI通知"""

        def _run() -> None:
            for func in self._listeners:
                try:
                    func()
                except ValueError as e:
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
