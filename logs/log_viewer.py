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
import subprocess
from pathlib import Path
from typing import Any
from env_paths import LOGS_DIR

from logs.log_searcher import load_logs, summarize


class LogViewer:
    """ログファイルを読み込んで表示するシンプルなGUIアプリ"""
    def __init__(self, parent: tk.Tk, path: Path) -> None:
        self.root: tk.Tk = parent
        self.root.title("Log Viewer")
        # Treeview(一覧表示)の設定
        self.tree = ttk.Treeview(
            self.root, columns=("time", "type", "trace_id", "message"), show="headings"
        )
        # タグごとに色を設定
        self.tree.tag_configure("ERROR", foreground="red")
        self.tree.tag_configure("CRITICAL", foreground="red")
        self.tree.tag_configure("WARNING", foreground="orange")
        self.tree.tag_configure("TRACE_JUMP", foreground="blue")
        self.tree.tag_configure("REBOOT", foreground="purple")

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
                    self.format_event(row),  # ← ★これも変更（イベントの内容をわかりやすく表示する）
                ),
                tags=(row["type"],),
            )

        self.tree.bind("<<TreeviewSelect>>", self.on_click)

    # ============================
    # 🔹 イベント処理
    # ============================
    def format_event(self, event: dict[str, Any]) -> str:
        """イベントの内容をわかりやすく表示する"""
        t: str | None = event.get("type")

        if t == "TRACE_JUMP":
            d: dict[str, Any] = event.get("data", {})
            return f"{d.get('from')} → {d.get('to')}"

        if t == "ERROR":
            return f"ERROR: {event.get('message')}"

        return event.get("message", "")

    # ============================
    # 🔹 その他のイベント処理
    # ============================
    # ここに他のイベント処理関数を追加していく
    def open_in_vscode(self, file: str, line: int) -> None:
        """VSCodeで該当行を開く"""
        subprocess.run(["code", "-g", f"{file}:{line}"])

    # ============================
    # 🔹 行クリックイベント
    # ============================
    def on_click(self, _event: tk.Event) -> None:
        """行がクリックされたときに詳細ウィンドウを表示する"""
        selected: tuple[str, ...] = self.tree.selection()
        if not selected:
            return

        index = int(selected[0])
        row: dict[str, Any] = self.rows[index]
        raw: dict[str, Any] = row.get("raw", {})

        detail = tk.Toplevel(self.root)
        detail.title("Detail")

        frame = tk.Frame(detail)
        frame.pack(fill=tk.BOTH, expand=True)

        # ===== 上部：要約 =====
        summary = tk.Label(
            frame,
            text=f"{row['type']} | {row['time']}",
            font=("Arial", 12, "bold"),
        )
        summary.pack(anchor="w")

        # ===== where情報 =====
        where: dict[str, Any] = raw.get("where", {})

        where_text: str = (
            f"File: {where.get('file')}\n"
            f"Function: {where.get('function')}\n"
            f"Line: {where.get('line')}"
        )

        where_label = tk.Label(frame, text=where_text, justify="left")
        where_label.pack(anchor="w")

        # ===== context =====
        context: dict[str, Any] = raw.get("context", {})
        context_label = tk.Label(
            frame,
            text=f"Context: {context}",
            justify="left",
        )
        context_label.pack(anchor="w")

        btn = tk.Button(
            frame,
            text="Open in VSCode",
            command=lambda: self.open_in_vscode(
                where.get("file", ""),
                where.get("line", 1),
            ),
        )
        btn.pack()

        # ===== JSON =====
        text = tk.Text(frame, wrap="word")
        text.pack(fill=tk.BOTH, expand=True)

        text.insert("1.0", json.dumps(raw, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    root = tk.Tk()
    log_dir: Path = LOGS_DIR
    latest: Path = max(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime)
    app = LogViewer(root, latest)
    root.mainloop()
