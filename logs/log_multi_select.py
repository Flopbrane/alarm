# -*- coding: utf-8 -*-
"""複数のログファイルを選択するためのGUI"""
#########################
# Author: F.Kurokawa
# Description:
# 複数のログファイルを選択するためのGUI
#########################
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from pathlib import Path


class LogFileSelector:
    """複数のログファイルを選択するためのGUI"""
    def __init__(self, root: tk.Tk, log_dir: Path) -> None:
        self.root: tk.Tk = root
        self.log_dir: Path = log_dir
        self.result: list[Path] | None = None

        self.window = tk.Toplevel(root)
        self.window.title("Select Log Files")

        self._build_ui()

    def _build_ui(self) -> None:
        """UI構築"""
        # ファイル取得
        files: list[Path] = sorted(
            list(self.log_dir.glob("*.log")) + list(self.log_dir.glob("*.jsonl")),
            key=lambda p: p.stem,
        )
        print(f"LMS:file_list:{files}")
        self.files: list[Path] = files

        # Treeview
        self.tree = ttk.Treeview(self.window, columns=("date", "name"), show="headings")
        self.tree.heading("date", text="Date")
        self.tree.heading("name", text="File")

        self.tree.pack(fill=tk.BOTH, expand=True)

        # データ投入
        for i, f in enumerate(files):
            date_str: str = f.stem.replace("app_", "")
            self.tree.insert("", "end", iid=str(i), values=(date_str, f.name))

        # 複数選択可能
        self.tree.config(selectmode="extended")

        # ボタン
        btn_frame = tk.Frame(self.window)
        btn_frame.pack(fill=tk.X)

        tk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side=tk.LEFT)

    def _on_ok(self) -> None:
        """OKボタン押下時の処理"""
        selected: tuple[str, ...] = self.tree.selection()
        self.result = [self.files[int(i)] for i in selected]
        self.window.destroy()

    def _on_cancel(self) -> None:
        """Cancelボタン押下時の処理"""
        self.result = None
        self.window.destroy()

    def show(self) -> list[Path] | None:
        """ウィンドウを表示し、選択結果を返す"""
        self.root.wait_window(self.window)
        return self.result
