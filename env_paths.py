#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""共通パスとPyInstaller対応
(必ず、TOPレベルフォルダに置くこと)"""
#########################
# Author: F.Kurokawa
# Description:
# 共通パスとPyInstaller対応(チェック済み)
#########################


import sys
from pathlib import Path


# ==============================
# 🔹 ベースディレクトリ取得
# ==============================
def get_app_root() -> Path:
    """PyInstaller / Python 両対応で実行ディレクトリを返す"""
    if getattr(sys, "frozen", False):
        # PyInstaller 実行時
        return Path(sys.executable).parent
    else:
        # 通常の Python 実行時
        return Path(__file__).resolve().parent

BASE_DIR: Path = get_app_root()
# ==============================
# 🔹 データ保存パス
# ==============================
DATA_DIR: Path = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 🔹 永続化データ（ユーザー状態）
ALARM_PATH: Path = DATA_DIR / "alarms.json"
STANDBY_PATH: Path = DATA_DIR / "standby.json"

# 🔥バックアップ用
BACKUP_DIR: Path = DATA_DIR / "backup"
BACKUP_DIR.mkdir(exist_ok=True)

# 🔥 config.json も同じ階層に置く
# 🔹 UI / 設定系
CONFIG_PATH: Path = DATA_DIR / "config.json"
CONFIG_PATH.parent.mkdir(exist_ok=True)
WINDOW_POSITION_PATH: Path = DATA_DIR / "window_positions.json"

# ==============================
# 🔹 ディレクトリ作成ユーティリティ
# ==============================
def ensure_dirs() -> None:
    """必要なディレクトリを作成"""
    DATA_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)
