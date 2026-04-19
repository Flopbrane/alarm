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
BASE_DIR: Path = Path(os.getenv("LOG_ROOT", str(Path(__file__).resolve().parent)))

# ログファイルを保存するディレクトリ。存在しない場合は自動で作成される
LOGS_DIR: Path = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
