# -*- coding: utf-8 -*-
"""保存JSONの入出力のみを扱うクラス"""
#########################
# Author: F.Kurokawa
# Description:
# alarm_storage.py(チェック済み)
#########################
from __future__ import annotations

# 標準モジュール
import json
import os
import shutil
import sys
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any, List, Literal, cast
from typing import TYPE_CHECKING
from tkinter import TclError, Tk, messagebox

# Local modules
from log_app import get_logger
from alarm_json_model import AlarmJson, AlarmStateJson
from env_paths import ALARM_PATH, BACKUP_DIR, STANDBY_PATH
# 実行時にも必要なもの
# 型だけ必要なもの
if TYPE_CHECKING:
    from logs.multi_info_logger import AppLogger


# 🔴 今後の注意点（今は問題なし）
# 1️⃣ JSON schema 変更時
# AlarmStateJson に field を追加したとき：
# load_standby
# save_standby
# この2点を 必ず同時に確認してください。
# （今は完璧に揃っています）

# =========================================================
# 🔹 JSON I/O 専用クラス（Dataclassを扱わない）
# =========================================================
class AlarmStorage:
    """📁 JSON保存・読み込み専用（Internalに触れない）"""
    _MAX_BACKUPS = 3

    @staticmethod
    def get_base_dir() -> Path:
        """PyInstaller or Python 実行フォルダ"""
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent

    def __init__(
        self,
        logger: AppLogger | None = None,
        alarm_path: Path | None = None,
        standby_path: Path | None = None,
    ) -> None:
        self.base_dir: Path = self.get_base_dir()
        self.logger: AppLogger = logger if logger else get_logger()
        self.alarm_path: Path = alarm_path or ALARM_PATH
        self.standby_path: Path = standby_path or STANDBY_PATH
        # ロガーは遅延初期化する（このクラスは起動直後から呼ばれるため、先にロガーを作ると循環参照になる可能性がある）

    def _show_dialog(
        self,
        title: str,
        message: str,
        level: Literal["info", "warning", "error"] = "info",
    ) -> None:
        """Tk のルートを一時生成してダイアログを表示する"""
        root: Tk | None = None
        try:
            root = Tk()
            root.withdraw()
            cast(Any, root).wm_attributes("-topmost", True)
            if level == "error":
                messagebox.showerror(title, message, parent=root)
            elif level == "warning":
                messagebox.showwarning(title, message, parent=root)
            else:
                messagebox.showinfo(title, message, parent=root)
            root.update_idletasks()
        except KeyboardInterrupt:
            return
        except TclError:
            print(f"[{level.upper()}] {title}: {message}")
        finally:
            if root is not None:
                root.destroy()

    # ==============================
    # 原子書き込み（atomic write）
    # ==============================
    def _atomic_write_json(
        self, path: Path, data: dict[str, list[dict[str, Any]]]
    ) -> None:
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
        raw_any: (
            Any  # 本来ならDict[str, Any]なんだけど、ファイル破損の可能性も考慮している
        )

        # alarm.json が無い / 空ファイルの場合は初回起動候補として案内する
        if not self.alarm_path.exists() or self.alarm_path.stat().st_size == 0:
            self._show_dialog(
                "初回起動の確認",
                "初回起動ではありませんか？アラームデータを記述してください",
                level="info",
            )
            return []
        # alarm.jsonが破損している場合[]を返す
        try:
            with open(self.alarm_path, "r", encoding="utf-8") as f:
                raw_any = json.load(f)
        except JSONDecodeError as e:
            self.logger.error(
                f"[ERROR] alarm.json が壊れています: {e}",
                context={"path": str(self.alarm_path)},
            )
            self._show_dialog(
                "alarm記録ファイルエラー",
                "alarm記録ファイルが破損しています",
                level="error",
            )
            return []

        if not isinstance(raw_any, dict):
            self.logger.error(
                "[ERROR] alarm.json format invalid (not dict)",
                context={"path": str(self.alarm_path)},
            )
            self._show_dialog(
                "alarm記録ファイルエラー",
                "alarm記録ファイルが破損しています",
                level="error",
            )
            return []

        alarms: list[AlarmJson] = []
        raw: dict[str, Any] = cast(dict[str, Any], raw_any)

        for a in raw.get("alarms", []):
            try:
                alarms.append(AlarmJson(**a))
            except TypeError as e:
                self.logger.warning(
                    f"[WARN] alarm entry skipped: {e}",
                )
                continue
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
        raw_any: (
            Any  # 本来ならDict[str, Any]なんだけど、ファイル破損の可能性も考慮してのAny
        )
        raw: dict[
            str, Any
        ]  # standby.jsonのPathがない(standby.jsonが存在しない)場合、[]を返す
        # standby_raw は list になる前提で later cast する
        standby_raw: Any  # standby.jsonのstandbyキーがlistでない場合、[]を返す
        states: list[AlarmStateJson] = []  # standby.jsonの初期化
        state: AlarmStateJson | None = (
            None  # standby.jsonの中身がdictでない場合、スキップする
        )
        s_dict: dict[str, Any]
        # standby.jsonが存在しない場合、[]を返す
        if not self.standby_path.exists():
            self.logger.info(
                "[INFO] standby.json が存在しません（初回起動の可能性）",
            )
            return []
        # raw_anyに取り敢えず読み込む。standby.jsonが破損している場合[]を返す
        try:
            with open(self.standby_path, "r", encoding="utf-8") as f:
                raw_any = json.load(f)
        except JSONDecodeError as e:
            self.logger.error(
                f"[ERROR] standby.json が壊れています: {e}",
            )
            return []
        # ① dict か？
        if not isinstance(raw_any, dict):
            self.logger.error(
                "[ERROR] standby.json format invalid (not dict)",
            )
            return []
        # ② dict として信じる
        raw = cast(
            dict[str, Any], raw_any
        )  # 第一段階のDict["standby", Any](このAnyはlist[Dict[str, Any]])
        # ③ standby は list か？
        standby_raw: Any = raw.get("standby", [])
        if not isinstance(standby_raw, list):
            self.logger.error(
                "[ERROR] standby.json format invalid (standby not list)",
            )
            return []
        standby_raw = cast(list[dict[str, Any]], standby_raw)
        # ④ list の中身は dict か？
        for s in standby_raw:
            if not isinstance(s, dict):
                self.logger.warning(
                    "[WARN] invalid standby entry skipped (not dict)",
                )
                continue
            s_dict = cast(dict[str, Any], s)
            try:
                state = AlarmStateJson(**s_dict)
                states.append(state)
            except TypeError as e:
                self.logger.warning(
                    f"[WARN] standby entry skipped: {e}",
                )
                continue
        return states

    # ==============================
    # 💾 Save — AlarmJson[]
    # ==============================
    def save_alarms(self, alarms: List[AlarmJson]) -> None:
        """alarmsの保存"""
        try:
            self._atomic_write_json(
                self.alarm_path,
                {"alarms": [a.__dict__ for a in alarms]},
            )
        except OSError as e:
            self.logger.error(
                f"[ERROR] alarms.json の保存に失敗: {e}",
            )
            raise

    # ==============================
    # 💾 Save — Standby[] only
    # ==============================
    def save_standby(self, states: List[AlarmStateJson]) -> None:
        """standbyの保存"""
        try:
            self._atomic_write_json(
                self.standby_path,
                {"standby": [s.__dict__ for s in states]},
            )
        except OSError as e:
            self.logger.error(
                f"[ERROR] standby.json の保存に失敗: {e}",
            )
            raise

    # ================================
    # 💾 Save all — Alarms[]+Standby[]
    # ================================
    def save_all(self, alarms: List[AlarmJson], states: List[AlarmStateJson]) -> None:
        """alarms の ID 並びに対し state がないものだけ生成"""
        exist_ids: set[str] = {s.id for s in states if s.id}
        for a in alarms:
            if a.id not in exist_ids:
                states.append(AlarmStateJson(id=a.id))

        try:
            self.save_alarms(alarms)
            self.save_standby(states)
        except OSError as e:
            self.logger.error(
                f"[ERROR] save_all の保存に失敗: {e}",
            )
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

            if self.alarm_path.exists():
                shutil.copy2(self.alarm_path, BACKUP_DIR / f"alarms_{ts}.json")
            else:
                self.logger.warning(
                    "[WARN] backup skipped: alarms.json not found",
                )

            if self.standby_path.exists():
                shutil.copy2(self.standby_path, BACKUP_DIR / f"standby_{ts}.json")
            else:
                self.logger.warning(
                    "[WARN] backup skipped: standby.json not found",
                )

            self.logger.info(
                f"💾 バックアップ保存 → {BACKUP_DIR}",
                )
        except OSError as e:
            # 🔥 ここで raise しない
            self.logger.warning(
                f"[WARN] backup failed: {e}",
                )

    # ===============================
    # 🔥 Restore — 最新ペアを完全復元
    # ===============================
    def restore_latest(self) -> None:
        """AlarmJson + AlarmStateJson の最新ペアを復元（失敗しても raise しない）"""
        try:
            backups: List[Path] = sorted(BACKUP_DIR.glob("alarms_*.json"), reverse=True)

            if not backups:
                self.logger.warning(
                    "⚠ 復元できるバックアップがありません",
                )
                return

            latest_ts: str = backups[0].stem.replace("alarms_", "")
            alarms_file: Path = BACKUP_DIR / f"alarms_{latest_ts}.json"
            standby_file: Path = BACKUP_DIR / f"standby_{latest_ts}.json"

            if alarms_file.exists() and standby_file.exists():
                shutil.copy2(alarms_file, self.alarm_path)
                shutil.copy2(standby_file, self.standby_path)
                self.logger.info(
                    f"♻ 復元完了 → {latest_ts}",
                    )
            else:
                self.logger.warning(
                    "⚠ 完全なバックアップペアが見つかりません",
                    )
        except OSError as e:
            self.logger.error(
                f"[ERROR] restore failed: {e}",
                )
