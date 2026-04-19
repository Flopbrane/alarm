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
<<<<<<< HEAD
from logs.log_viewer_elder import LogViewer
=======
from logs.log_viewer_past import LogViewer
>>>>>>> 67c2bf68dce35d0f1da5d3f5f1d779ac2502ca33


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
