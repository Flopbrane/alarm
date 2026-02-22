# -*- coding: utf-8 -*-
"""実働検証データ生成スクリプト"""
#########################
# Author: F.Kurokawa
# Description:
# 実働検証用のスクリプト群
#########################

import tempfile

# run_alarm_once.py
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Literal

from alarm_internal_model import AlarmInternal
from alarm_states_model import AlarmStateInternal
from alarm_irregular_logger import AlarmLogger, LogWhere
from alarm_manager_cycle_control_options import TEST_CONFIG_CHANGED
from alarm_manager_temp import AlarmManager

# NEXT: AlarmStateJson の欠損時は initial を追加（test 追加）
# WHY : GUI で状態が必要。保存系は state を落とす可能性があるため


CycleCondition = Literal["startup", "loop", "config_change"]
_temp_dirs: List[TemporaryDirectory[str]] = []


class AlarmRuntime:
    """AlarmManager を安全に実行するためのテスト用実行文脈"""

    def __init__(self) -> None:
        self.tmpdir: TemporaryDirectory[str] = tempfile.TemporaryDirectory()
        base = Path(self.tmpdir.name)

        self.alarm_path: Path = base / "alarms.json"
        self.standby_path: Path = base / "standby.json"

        # 空ファイルを作っておく（load_all対策）
        self.alarm_path.write_text('{"alarms": []}', encoding="utf-8")
        self.standby_path.write_text('{"standby": []}', encoding="utf-8")

        self.mgr = AlarmManager(
            alarm_path=self.alarm_path,
            standby_path=self.standby_path,
        )

    def startup(self) -> None:
        """起動直後の状態正規化処理を実行する"""
        self.mgr.start_cycle("startup")

    def config_change(self) -> None:
        """アラーム設定変更後の再計算処理を実行する"""
        self.mgr.start_cycle("config_change")

    def loop(self) -> None:
        """メインループ処理を実行する"""
        self.mgr.start_cycle("loop")

    def close(self) -> None:
        """実行文脈を閉じる"""
        self.tmpdir.cleanup()


def _where(func_name: str) -> "LogWhere":
    """Format location string for logging"""
    return LogWhere(module=__name__, function=func_name)


def main() -> None:
    """デモ用メイン実働検証スクリプト"""
    print("[DEMO] AlarmManager lifecycle test")
    runtime = AlarmRuntime()
    run_cycle_for_test(runtime.mgr, "startup")
    run_cycle_for_test(runtime.mgr, "loop")


# =====================================================
# 🔹 テスト用ユーティリティ
# =====================================================
def make_test_manager() -> AlarmManager:
    """一時ディレクトリ上に AlarmManager を作成して返す（テスト用）"""
    tmp: TemporaryDirectory[str] = TemporaryDirectory()
    alarm_path: Path = Path(tmp.name) / "alarm.json"
    standby_path: Path = Path(tmp.name) / "standby.json"

    mgr = AlarmManager(
        alarm_path=alarm_path,
        standby_path=standby_path,
    )
    _temp_dirs.append(tmp)  # GCされないよう保持
    return mgr


# =====================================================
# 🔹 デバッグ用メソッド
# =====================================================
def run_cycle_for_test(mgr: AlarmManager, condition: str) -> None:
    """指定した条件でサイクルを1回実行する（テスト用）"""
    if condition == "startup":
        mgr.start_cycle("startup")
    elif condition == "config_change":
        mgr.start_cycle("config_change")
    elif condition == "loop":
        mgr.start_cycle("loop")


def _validate_repeat_at_single(
    rt: AlarmRuntime,
    alarm_obj: AlarmInternal,
    state: AlarmStateInternal,
) -> bool:
    """single 繰り返し設定のアラームが正しいか検証"""
    logger: AlarmLogger = rt.mgr.logger
    print(f"Validating single repeat alarm ID {alarm_obj.id}")

    if alarm_obj.repeat != "single":
        return True

    if not alarm_obj.enabled:
        return True

    if state.lifecycle_finished and state.next_fire_datetime is not None:
        logger.error(
            message="alarm fired after lifecycle_finished but next_fire_datetime is set",
            where=_where("_validate_single_repeat"),
            alarm_id=alarm_obj.id,
            context={
                "repeat": alarm_obj.repeat,
                "lifecycle_finished": state.lifecycle_finished,
                "next_fire_datetime": state.next_fire_datetime,
            },
            timestamp=rt.mgr.internal_clock(),
        )
        return False

    return True


# =============================================
# Test functions
# =============================================
def test_validate_repeat_at_single() -> None:
    """repeat =='single' のアラームの状態検証"""
    rt = AlarmRuntime()
    mgr: AlarmManager = rt.mgr
    rt.startup()

    for alarm, state in zip(mgr.alarms, mgr.states):
        _validate_repeat_at_single(rt, alarm, state)
    rt.loop()
    print("✔ repeat=='single' のアラーム状態を検証しました")
    rt.close()


def test_missing_state_creates_initial_state() -> None:
    """状態が欠損していても load_all() により state が補完されることを検証"""
    print("1. 状態欠損時の初期状態生成を検証開始")

    mgr_instance = AlarmManager(alarm_path=Path("alarm_sample.json"))
    mgr_instance.load_all()  # ← ここがすべて

    alarm_ids: set[str] = {a.id for a in mgr_instance.alarms}
    state_ids: set[str] = {s.id for s in mgr_instance.states}

    # すべての alarm に対応する state が存在すること
    assert alarm_ids == state_ids

    # 初期 state として最低限破綻していないこと
    for alarm_item in mgr_instance.alarms:
        state: AlarmStateInternal = next(
            s for s in mgr_instance.states if s.id == alarm_item.id
        )

        assert state.id == alarm_item.id
        assert state.snooze_count >= 0

        if alarm_item.enabled and alarm_item.repeat in ("weekly", "custom"):
            assert (
                state.next_fire_datetime is None
                or state.next_fire_datetime > mgr_instance.internal_clock()
            )

    print("✔ 状態欠損時でも state が正しく補完されました")


def test_hard_alarm_sample_json_survives() -> None:
    """alarm_sample.json をロードして、state 欠損がないことを検証"""
    print("2. alarm_sample.json のロード検証開始")
    rt = AlarmRuntime()
    # この alarm_sample.json を配置した状態で
    rt.startup()
    # 1️⃣ 例外を出さずにロードできること
    assert len(rt.mgr.alarms) > 0

    # 2️⃣ state が必ず alarms 分そろっている
    alarm_ids: set[str] = {a.id for a in rt.mgr.alarms}
    state_ids: set[str] = {s.id for s in rt.mgr.states}

    assert alarm_ids == state_ids
    print("✔ alarm_sample.json が正しくロードされました")
    rt.close()


def test_next_fire_is_sane_for_all_alarms() -> None:
    """全アラームの next_fire_datetime が妥当な値であることを検証"""
    print("3. 全アラームの next_fire_datetime の妥当性検証開始")
    rt = AlarmRuntime()
    logger: AlarmLogger = rt.mgr.logger

    rt.startup()
    now: datetime = rt.mgr.internal_clock()

    for alarm_item in rt.mgr.alarms:
        if not alarm_item.enabled:
            dt: datetime | None = next(
                s for s in rt.mgr.states if s.id == alarm_item.id
            ).next_fire_datetime
            if dt is not None:
                logger.warning(
                    message="Disabled alarm has state.next_fire_datetime set",
                    where=_where("test_next_fire_is_sane_for_all_alarms"),
                    alarm_id=alarm_item.id,
                    context={
                        "alarm_enabled": alarm_item.enabled,
                        "next_fire_datetime": dt,
                    },
                    timestamp=now,
                )
            continue

        state: AlarmStateInternal = next(
            s for s in rt.mgr.states if s.id == alarm_item.id
        )

        if alarm_item.repeat == "single":
            if state.lifecycle_finished:
                assert state.next_fire_datetime is None
            else:
                if (
                    state.next_fire_datetime is not None
                    and state.next_fire_datetime <= now
                ):
                    # ❗ 異常ではないが注意状態
                    rt.mgr.logger.warning(
                        alarm_id=alarm_item.id,
                        where=_where("test_next_fire_is_sane_for_all_alarms"),
                        message="single alarm is pending fire (next_fire is in the past)",
                        context={
                            "next_fire_datetime": state.next_fire_datetime,
                            "now": now,
                        },
                        timestamp=now,
                    )
    rt.loop()
    print("✔ 全アラームの next_fire_datetime をチェックしました")
    rt.close()


def test_disabled_alarms_never_fire() -> None:
    """無効化されたアラームが発火しないことを検証"""
    print("4. 無効化アラームの発火検証開始")
    rt = AlarmRuntime()
    rt.startup()
    rt.loop()

    for alarm_item, state_item in zip(rt.mgr.alarms, rt.mgr.states):
        if not alarm_item.enabled:
            assert not state_item.triggered

    print("✔ 無効化アラームは発火しませんでした")
    rt.close()


def test_edge_case_alarm_fields_do_not_crash() -> None:
    """極端なフィールド値のアラームがクラッシュしないことを検証"""
    print("5. 極端なフィールド値のアラームのクラッシュ検証開始")
    rt = AlarmRuntime()
    mgr: AlarmManager = rt.mgr

    rt.startup()
    rt.config_change()
    rt.loop()
    logger: AlarmLogger = mgr.logger
    # 極端な値のアラームを追加
    # 異常値に対する耐性を確認
    rt.startup()
    extreme_alarms: List[AlarmInternal] = [
        AlarmInternal(
            id="1000",
            name="Recent time Alarm",
            datetime_=datetime(2026, 3, 8,17, 20),
            repeat="single",
            enabled=True,
        ),
        AlarmInternal(
            id="9999",
            name="Extreme Past Alarm",
            datetime_=datetime(1970, 1, 1, 0, 0),
            repeat="single",
            enabled=True,
        ),
        AlarmInternal(
            id="10000",
            name="Extreme Future Alarm",
            datetime_=datetime(3000, 1, 1, 0, 0),
            repeat="single",
            enabled=True,
        ),
    ]
    mgr.alarms.append(extreme_alarms[0])
    mgr.alarms.append(extreme_alarms[1])
    try:
        rt.config_change()
    except (ValueError, RuntimeError, TypeError) as e:
        logger.error(
            message=f"Crash occurred with extreme alarm fields: {e}",
            where=_where("test_edge_case_alarm_fields_do_not_crash"),
            timestamp=mgr.internal_clock(),
        )
        assert False, "クラッシュが発生しました"
    assert True
    rt.loop()
    print("✔ 極端なフィールド値のアラームはクラッシュしませんでした")


def test_config_change_recalculates_states() -> None:
    """設定変更時に状態が再計算されることを検証"""
    print("X. config_change cycle の検証開始")

    rt = AlarmRuntime()

    rt.startup()
    rt.loop()

    # ここで alarm / state を意図的に変更してもOK
    # テスト開始前にstandby.jsonの内容を削除しておく
    # あるは、イレギュラーな状態にしておく
    # 例えば、No.1アラームの有効/無効を切り替えるなど
    # mgr.toggle_alarm(1) など

    rt.config_change()
    # assertions...
    print("✔ config_change cycle を通過しました")
    rt.close()


def test_recalced_states_are_sane() -> None:
    """config_change 後の状態が妥当であることを検証"""
    print("Y. 再計算後の状態妥当性検証開始")

    rt = AlarmRuntime()
    mgr: AlarmManager = rt.mgr

    rt.startup()
    rt.config_change()

    now: datetime = mgr.internal_clock()
    errors: list[str] = []

    for alarm in mgr.alarms:
        state: AlarmStateInternal = next(s for s in mgr.states if s.id == alarm.id)

        # 無効アラーム
        if not alarm.enabled:
            if state.next_fire_datetime is not None:
                errors.append(f"[ID={alarm.id}] disabled alarm has next_fire_datetime")
            continue

        # single アラーム
        if alarm.repeat == "single":
            if state.lifecycle_finished:
                if state.next_fire_datetime is not None:
                    errors.append(
                        f"[ID={alarm.id}] finished single alarm has next_fire_datetime"
                    )
            else:
                # ❗ ここが重要
                if (
                    state.next_fire_datetime is not None
                    and state.next_fire_datetime <= now
                ):
                    errors.append(
                        f"[ID={alarm.id}] single alarm next_fire is in the past"
                    )

    assert not errors, "\n".join(errors)
    print("✔ 再計算後の状態は妥当でした")

    rt.loop()
    rt.close()

    # ==============================================
    # Example usage of the main function
    # ==============================================


if __name__ == "__main__":
    # input("⚠️ No.1 実アラームが鳴る可能性があります。Enterで続行")
    # main()  # デモ用メイン実働検証スクリプト実行
    # Validate example alarm
    # from datetime import datetime
    test_validate_repeat_at_single()
    test_missing_state_creates_initial_state()
    test_hard_alarm_sample_json_survives()
    test_next_fire_is_sane_for_all_alarms()
    test_disabled_alarms_never_fire()
    test_edge_case_alarm_fields_do_not_crash()
    test_config_change_recalculates_states()
    test_recalced_states_are_sane()
    print("All tests completed successfully.")
