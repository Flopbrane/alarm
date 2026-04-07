# -*- coding: utf-8 -*-
"""ログファイルを読み込んで表示するシンプルなGUIアプリ"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Any

from .log_searcher import load_logs, summarize


class LogViewer:
    """ログファイルを読み込んで表示するシンプルなGUIアプリ"""
    def __init__(self, parent: tk.Tk, path: Path) -> None:
        self.root: tk.Tk = parent
        self.root.title("Log Viewer")

        self.tree = ttk.Treeview(
            self.root, columns=("time", "type", "trace_id", "message"), show="headings"
        )

        for col in ("time", "type", "trace_id", "message"):
            self.tree.heading(col, text=col.upper())

        self.tree.pack(fill=tk.BOTH, expand=True)

        logs: list[dict[str, Any]] = load_logs(path)
        self.rows: list[dict[str, Any]] = summarize(logs)

        for i, row in enumerate(self.rows):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    row["time"],
                    row["type"],
                    row["trace_id"],
                    row["message"],
                ),
            )

        self.tree.bind("<<TreeviewSelect>>", self.on_click)

    # ============================
    # 🔹 イベント処理
    # ============================
    @staticmethod
    def format_event(event: dict[str, Any]) -> str:
        """イベントをわかりやすい文字列に変換する"""
        if event["type"] == "TRACE_JUMP":
            return f"TRACE_JUMP: {event['from']} → {event['to']}"
        return "UNKNOWN"

    # ============================
    # 🔹 行クリックイベント
    # ============================
    def on_click(self, _event: tk.Event) -> None:
        """行がクリックされたときのハンドラ"""
        selected: tuple[str, ...] = self.tree.selection()
        if not selected:
            return

        index = int(selected[0])
        row: dict[str, Any] = self.rows[index]

        detail = tk.Toplevel(self.root)
        detail.title("Detail")

        text = tk.Text(detail, wrap="word")
        text.pack(fill=tk.BOTH, expand=True)

        text.insert("1.0", json.dumps(row["raw"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    root = tk.Tk()
    app = LogViewer(root, Path("logs/app_log.jsonl"))
    root.mainloop()
