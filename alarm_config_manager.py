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
    cfg: Config = ConfigManager.load_config()
    cfg.default_mode = mode
    ConfigManager.save_config(cfg)

def set_last_mode(mode: Mode) -> None:
    """最終モードを変更"""
    cfg: Config = ConfigManager.load_config()
    cfg.last_mode = mode
    ConfigManager.save_config(cfg)

# ==============================
# 🔹 Config dataclass 定義
# ==============================
@dataclass
class Config:
    """config.json の型定義"""
    default_mode: Mode = DEFAULT_MODE  # gui / cui / dialog
    last_mode: Mode = LAST_MODE  # gui / cui / dialog
    show_dialog: bool = True  # 起動モード選択ダイアログを表示するかどうか

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
                return s
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
            cfg = Config()
            ConfigManager.save_config(cfg)
            return cfg

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

                cfg = Config(
                    default_mode=default_mode,
                    last_mode=last_mode,
                    show_dialog=show_dialog,
                )

            return cfg

        except (IOError, OSError, json.JSONDecodeError) as e:
            messagebox.showwarning("Config", f"Failed to load config: {e}, using defaults")
            cfg = Config()
            ConfigManager.save_config(cfg)
            return cfg

    @staticmethod
    def save_config(cfg: Config) -> None:
        """config.json 保存"""
        Path(CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)

# ==============================
