# -*- coding: utf-8 -*-
"""ログのパスを管理するモジュール"""
#########################
# Author: F.Kurokawa
# Description:
# rootとログフォルダのパスを管理するモジュール
#########################
import os
from pathlib import Path

# BASE_DIRは環境変数LOG_ROOTから取得。指定がない場合はこのファイルの親ディレクトリを使用する
env_root: str | None = os.getenv("LOG_ROOT")

if env_root is not None:
    base_f: Path = Path(env_root).resolve()
else:
    base_f = Path(__file__).resolve().parent.parent

BASE_DIR: Path =base_f
LOGS_DIR: Path = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
