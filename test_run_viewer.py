# -*- coding: utf-8 -*-
"""logs/log_viewer.py のテストコード"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################

# run_viewer.py
from pathlib import Path
import tkinter as tk

from env_paths import LOGS_DIR
from logs.log_viewer_elder import LogViewer


def main() -> None:
    """VSCode用デバッグテストコード"""
    root = tk.Tk()

    log_dir: Path = LOGS_DIR
    candidates: list[Path] = list(log_dir.glob("*.jsonl")) or list(log_dir.glob("*.log"))

    if not candidates:
        raise RuntimeError("ログファイルが見つかりません")

    latest: Path = max(candidates, key=lambda p: p.stat().st_mtime)

    LogViewer(root, latest)
    root.mainloop()


if __name__ == "__main__":
    main()
