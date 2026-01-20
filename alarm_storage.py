# -*- coding: utf-8 -*-
"""保存JSONの入出力のみを扱うクラス"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_storage.py(チェック済み)
#########################
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, List, cast

from alarm_json_model import AlarmJson, AlarmStateJson
from env_paths import ALARM_PATH, BACKUP_DIR, STANDBY_PATH


# =========================================================
# 🔹 JSON I/O 専用クラス（Dataclassを扱わない）
# =========================================================
class AlarmStorage:
    """📁 JSON保存・読み込み専用（Internalに触れない）"""
    # ==============================
    # 原子書き込み（atomic write）
    # ==============================
    def _atomic_write_json(self, path: Path, data: dict[str, list[dict[str, Any]]]) -> None:
        """不可分（atomic）なJSON書き込み。途中状態を残さない。"""
        tmp: Path = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(path)

    # ==============================
    # 📥 Load — AlarmJson[]
    # ==============================
    def load_alarms(self) -> List[AlarmJson]:
        """alarmsの読み込み"""
        raw_any: Any  # 本来ならDict[str, Any]なんだけど、ファイル破損の可能性も考慮している

        # alarm.jsonのPathがない(alarm.jsonが存在しない)場合、[]を返す
        if not ALARM_PATH.exists():
            print("[INFO] alarm.json が存在しません（初回起動の可能性）")
            return []
        # alarm.jsonが破損している場合[]を返す
        try:
            with open(ALARM_PATH, "r", encoding="utf-8") as f:
                raw_any = json.load(f)
        except JSONDecodeError as e:
            print(f"[ERROR] alarm.json が壊れています: {e}")
            return []

        if not isinstance(raw_any, dict):
            print("[ERROR] alarm.json format invalid (not dict)")
            return []

        alarms: list[AlarmJson] = []
        raw: dict[str, Any] = cast(dict[str, Any], raw_any)

        for a in dict(raw).get("alarms", []):
            try:
                alarms.append(AlarmJson(**a))
            except TypeError as e:
                print(f"[WARN] alarm entry skipped: {e}")
        return alarms

    # ==============================
    # 📥 Load — Standby State[]
    # ==============================
    def load_standby(self) -> list[AlarmStateJson]:
        """standbyの読み込み
        raw_any = dict[
            str,                # key
            list[dict[str, Any]]  # value の一例(ここのAnyは"str|int|bool|list")
        ]
        """
        raw_any: Any  # 本来ならDict[str, Any]なんだけど、ファイル破損の可能性も考慮してのAny
        raw: dict[str, Any]  # standby.jsonのPathがない(standby.jsonが存在しない)場合、[]を返す
        # standby_raw は list になる前提で later cast する
        standby_raw: Any  # standby.jsonのstandbyキーがlistでない場合、[]を返す
        states: list[AlarmStateJson] = [] # standby.jsonの初期化
        state: AlarmStateJson|None = None # standby.jsonの中身がdictでない場合、スキップする
        s_dict: dict[str, Any]
        # standby.jsonが存在しない場合、[]を返す
        if not STANDBY_PATH.exists():
            print("[INFO] standby.json が存在しません（初回起動の可能性）")
            return []
        # raw_anyに取り敢えず読み込む。standby.jsonが破損している場合[]を返す
        try:
            with open(STANDBY_PATH, "r", encoding="utf-8") as f:
                raw_any = json.load(f)
        except JSONDecodeError as e:
            print(f"[ERROR] standby.json が壊れています: {e}")
            return []
        # ① dict か？
        if not isinstance(raw_any, dict):
            print("[ERROR] standby.json format invalid (not dict)")
            return []
        # ② dict として信じる
        raw = cast(dict[str, Any], raw_any) # 第一段階のDict["standby", Any](このAnyはlist[Dict[str, Any]])
        # ③ standby は list か？
        standby_raw: Any = raw.get("standby", [])
        if not isinstance(standby_raw, list):
            print("[ERROR] standby.json format invalid (standby not list)")
            return []
        standby_raw = cast(list[dict[str, Any]], standby_raw)
        # ④ list の中身は dict か？
        for s in standby_raw:
            if not isinstance(s, dict):
                print("[WARN] invalid standby entry skipped (not dict)")
                continue
            s_dict = cast(dict[str, Any], s)
            try:
                state = AlarmStateJson(**s_dict)
                states.append(state)
            except TypeError as e:
                print(f"[WARN] standby entry skipped: {e}")

        return states

    # ==============================
    # 💾 Save — AlarmJson[]
    # ==============================
    def save_alarms(self, alarms: List[AlarmJson]) -> None:
        """alarmsの保存"""
        try:
            self._atomic_write_json(
                ALARM_PATH,
                {"alarms": [a.__dict__ for a in alarms]},
            )
        except OSError as e:
            print(f"[ERROR] alarms.json の保存に失敗: {e}")
            raise

    # ==============================
    # 💾 Save — Standby[] only
    # ==============================
    def save_standby(self, states: List[AlarmStateJson]) -> None:
        """standbyの保存"""
        try:
            self._atomic_write_json(
                STANDBY_PATH,
                {"standby": [s.__dict__ for s in states]},
            )
        except OSError as e:
            print(f"[ERROR] standby.json の保存に失敗: {e}")
            raise

    # ==============================
    # 💾 Save all — Alarms[]+Standby[]
    # ==============================
    def save_all(self, alarms: List[AlarmJson], states: List[AlarmStateJson]) -> None:
        """alarms の ID 並びに対し state がないものだけ生成"""
        exist_ids: set[int] = {s.id for s in states}
        for a in alarms:
            if a.id not in exist_ids:
                states.append(AlarmStateJson(id=a.id))

        try:
            self.save_alarms(alarms)
            self.save_standby(states)
        except OSError as e:
            print(f"[ERROR] save_all の保存に失敗: {e}")
            raise  # 将来、loggerを作成したときにログ出力に変える
        else:
            self.backup()
    # ==========backup関連============

    # ===============================
    # 🔥 Backup — alarms + standby 両方保存
    # ===============================
    def backup(self) -> None:
        """alarms と standby のバックアップ（失敗しても致命ではない）"""
        try:
            BACKUP_DIR.mkdir(exist_ok=True)
            ts: str = datetime.now().strftime("%Y%m%d_%H%M%S")

            if ALARM_PATH.exists():
                shutil.copy2(ALARM_PATH, BACKUP_DIR / f"alarms_{ts}.json")
            else:
                print("[WARN] backup skipped: alarms.json not found")

            if STANDBY_PATH.exists():
                shutil.copy2(STANDBY_PATH, BACKUP_DIR / f"standby_{ts}.json")
            else:
                print("[WARN] backup skipped: standby.json not found")

            print(f"💾 バックアップ保存 → {BACKUP_DIR}")

        except OSError as e:
            # 🔥 ここで raise しない
            print(f"[WARN] backup failed: {e}")

    # ===============================
    # 🔥 Restore — 最新ペアを完全復元
    # ===============================
    def restore_latest(self) -> None:
        """AlarmJson + AlarmStateJson の最新ペアを復元（失敗しても raise しない）"""
        try:
            backups: List[Path] = sorted(BACKUP_DIR.glob("alarms_*.json"), reverse=True)

            if not backups:
                print("⚠ 復元できるバックアップがありません")
                return

            latest_ts: str = backups[0].stem.replace("alarms_", "")
            alarms_file: Path = BACKUP_DIR / f"alarms_{latest_ts}.json"
            standby_file: Path = BACKUP_DIR / f"standby_{latest_ts}.json"

            restored = False

            if alarms_file.exists():
                shutil.copy2(alarms_file, ALARM_PATH)
                restored = True
            else:
                print(f"[WARN] alarms backup missing: {alarms_file}")

            if standby_file.exists():
                shutil.copy2(standby_file, STANDBY_PATH)
                restored = True
            else:
                print(f"[WARN] standby backup missing: {standby_file}")

            if restored:
                print(f"♻ 復元完了 → {latest_ts}")
            else:
                print("⚠ 復元に失敗しました（有効なファイルなし）")

        except OSError as e:
            print(f"[ERROR] restore failed: {e}")
