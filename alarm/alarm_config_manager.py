# -*- coding: utf-8 -*-
"""configの設定・保存・読み込み・編集"""
#########################
# Author: F.Kurokawa
# Description:
# config manager（チェック済み）
#########################

from __future__ import annotations  # noqa: I001

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import messagebox
from typing import Any, Final, Literal, TypeAlias, TypeGuard

from env_paths import CONFIG_PATH

# =========================================================
# 🔹 config.json の該当値以外を排除
# =========================================================
Mode: TypeAlias = Literal["gui", "cui", "dialog"]
DEFAULT_MODE: Final[Mode] = "dialog"
LAST_MODE: Final[Mode] = "dialog"

def set_default_mode(mode: Mode) -> None:
    """デフォルトモードを変更"""
    config: Config = ConfigManager.load_config()
    config.default_mode = mode
    ConfigManager.save_config(config)

def set_last_mode(mode: Mode) -> None:
    """最終モードを変更"""
    config: Config = ConfigManager.load_config()
    config.last_mode = mode
    ConfigManager.save_config(config)

# ==============================
# 🔹 Config dataclass 定義
# ==============================
@dataclass
class Config:
    """config.json の型定義"""
    default_mode: Mode = DEFAULT_MODE  # gui / cui / dialog
    last_mode: Mode = LAST_MODE  # gui / cui / dialog
    show_dialog: bool = True  # 起動モード選択ダイアログを表示するかどうか
    # 🔴 追加
    last_shutdown_clean: bool = True  # 前回正常終了フラグ
    tick_interval_sec: float = 1.0
    auto_start: bool = True
    last_boot_time: float = 0.0

# ==============================
# 🔹 ConfigManager クラス
# ==============================
class ConfigManager:
    """config.json を管理するクラス"""

    @staticmethod
    def _normalize_mode(v: Any) -> Mode:
        """mode の正規化"""
        if isinstance(v, str):
            s: str = v.lower()
            if s in ("gui", "cui", "dialog"):
                return s  # type: ignore[return-value]
        return DEFAULT_MODE

    # 🔸 config.json
    @staticmethod
    def get_config_path() -> Path:
        """config.json のフルパス"""
        return CONFIG_PATH

    @staticmethod
    def load_config() -> Config:
        """config.json 読込"""
        path: Path = ConfigManager.get_config_path()

        if not path.exists():
            cfg_local = Config()
            ConfigManager.save_config(cfg_local)
            return cfg_local

        def is_dict_str_any(v: Any) -> TypeGuard[dict[str, Any]]:
            return isinstance(v, dict)

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw: Any = json.load(f)

                if not is_dict_str_any(raw):
                    raise ValueError("config.json の形式が不正です")

                data: dict[str, Any] = raw
                default_mode: Mode = ConfigManager._normalize_mode(data.get("default_mode"))
                last_mode: Mode = ConfigManager._normalize_mode(data.get("last_mode"))
                show_dialog = bool(data.get("show_dialog", True))
                last_shutdown_clean = bool(data.get("last_shutdown_clean", True))
                last_boot_time = float(data.get("last_boot_time", 0.0))
                cfg_local = Config(
                    default_mode=default_mode,
                    last_mode=last_mode,
                    show_dialog=show_dialog,
                    last_shutdown_clean=last_shutdown_clean,
                    last_boot_time=last_boot_time,
                )

            return cfg_local

        except (IOError, OSError, json.JSONDecodeError) as e:
            messagebox.showwarning("Config", f"Failed to load config: {e}, using defaults")
            cfg_local = Config()
            ConfigManager.save_config(cfg_local)
            return cfg_local

    @staticmethod
    def save_config(config: Config) -> None:
        """config.json 保存"""
        Path(CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, ensure_ascii=False, indent=2)

# ==============================
# 🔹 動作確認用コード(デバッグ用)
# ==============================
# if __name__ == "__main__":
#     cfg: Config = ConfigManager.load_config()
#     print(cfg)

#     cfg.last_shutdown_clean = False
#     ConfigManager.save_config(cfg)

#     print("config.json を書き換えました")
