# -*- coding: utf-8 -*-
"""ログ表示GUI（安定版）"""

from __future__ import annotations

from datetime import datetime
import json
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any, Final, TypeAlias, Union, cast

from env_paths import LOGS_DIR
from logs.log_searcher import summarize, collect_logs
from logs.log_storage import load_log
from logs.time_utils import to_jst_datetime


LogRow: TypeAlias = dict[str, Any]
LogRows: TypeAlias = list[LogRow]
ParentWidget = Union[tk.Tk, tk.Toplevel]

class LogFileSelector:
    """ログファイル一覧を表示し、複数選択させるダイアログ"""

    def __init__(self, parent: ParentWidget, log_dir: Path) -> None:
        self.parent = parent
        self.log_dir: Path = log_dir

    def show(self) -> list[Path] | None:
        """ログファイル一覧を表示し、選択結果を返す"""
        window = tk.Toplevel(self.parent)
        window.title("ログ選択")
        window.geometry("700x500")
        window.transient(self.parent)
        window.grab_set()

        files: list[Path] = sorted(
            list(self.log_dir.glob("*.jsonl")) +
            list(self.log_dir.glob("*.log")),
            key=lambda p: p.name
        )

        if not files:
            tk.Label(window, text="ログファイルが見つかりません").pack(
                padx=12,
                pady=12,
                anchor="w",
            )
            tk.Button(window, text="閉じる", command=window.destroy).pack(pady=8)
            window.wait_window()
            return None

        listbox = tk.Listbox(
            window,
            selectmode=tk.MULTIPLE,
            width=100,
            height=20,
            exportselection=False,
        )
        listbox.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        for file_path in files:
            listbox.insert(tk.END, file_path.name)

        selected_paths: list[Path] = []

        def on_open() -> None:
            """選択したLog_Pathを読み込む"""
            indices: tuple[int, ...] = listbox.curselection() # type: ignore
            for index in indices:  # type: ignore
                selected_paths.append(files[index])
            window.destroy()

        def on_cancel() -> None:
            """キャンセルボタン処理"""
            window.destroy()

        button_frame = tk.Frame(window)
        button_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        tk.Button(button_frame, text="開く", command=on_open).pack(side=tk.LEFT)
        tk.Button(button_frame, text="キャンセル", command=on_cancel).pack(
            side=tk.LEFT,
            padx=8,
        )

        window.wait_window()
        return selected_paths if selected_paths else None


class LogViewer:
    """ログファイルを表示するGUI"""

    TRACE_ALL: Final[str] = "trace.id_ALL"
    TYPE_ALL: Final[str] = "type_ALL"

    def __init__(self, parent: tk.Tk, initial_log_path: Path | None = None) -> None:
        self.root: tk.Tk = parent
        self.root.title("Log Viewer")
        self.root.geometry("1200x650+100+100")
        # 基本設定
        self.log_dir: Path = LOGS_DIR
        self.rows: LogRows = []
        self.rows_raw: LogRows = []
        self._single_click_after_id: str | None = None
        # 仕様別フィルタ
        self.trace_var = tk.StringVar(value=self.TRACE_ALL)
        self.type_var = tk.StringVar(value=self.TYPE_ALL)
        # フォント指定
        self.font_title: tuple[str, int, str] = ("Yu Gothic UI", 12, "bold")
        self.font_normal: tuple[str, int] = ("Yu Gothic UI", 10)
        self.font_bold_normal: tuple[str, int, str] = ("Yu Gothic UI", 10, "bold")
        self.font_mono: tuple[str, int] = ("Cascadia Code", 10)
        # 型だけ宣言
        self.trace_dropdown: ttk.Combobox
        self.type_dropdown: ttk.Combobox
        self.tree: ttk.Treeview
        # 画像描画
        self._build_ui()

        if initial_log_path is not None:
            self.reload_log(initial_log_path)

    # =======================
    # UI構築
    # =======================
    def _build_ui(self) -> None:
        """UIを構築する"""
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(top_frame, text="単一ログを開く", command=self.open_log_file).pack(
            side=tk.LEFT
        )
        tk.Button(top_frame, text="複数ログを開く", command=self.open_logs).pack(
            side=tk.LEFT,
            padx=8,
        )
        tk.Button(top_frame, text="フィルタ解除", command=self.reset_filters).pack(
            side=tk.LEFT
        )

        filter_frame = tk.Frame(self.root)
        filter_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        tk.Label(filter_frame, text="TRACE").pack(side=tk.LEFT)
        self.trace_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.trace_var,
            state="readonly",
            width=35,
        )
        self.trace_dropdown.pack(side=tk.LEFT, padx=(4, 12))
        self.trace_dropdown.bind("<<ComboboxSelected>>", self.apply_filter)

        tk.Label(filter_frame, text="TYPE").pack(side=tk.LEFT)
        self.type_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.type_var,
            state="readonly",
            width=20,
        )
        self.type_dropdown.pack(side=tk.LEFT, padx=(4, 12))
        self.type_dropdown.bind("<<ComboboxSelected>>", self.apply_filter)

        self.tree = ttk.Treeview(
            self.root,
            columns=("type", "time", "trace_id", "message"),
            show="headings",
        )
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self.tree.heading("type", text="TYPE")
        self.tree.heading("time", text="TIME")
        self.tree.heading("trace_id", text="TRACE_ID")
        self.tree.heading("message", text="MESSAGE")

        self.tree.column("type", width=120, anchor="w")
        self.tree.column("time", width=180, anchor="w")
        self.tree.column("trace_id", width=220, anchor="w")
        self.tree.column("message", width=640, anchor="w")

        self.tree.tag_configure(
            "INFO",
            foreground="black",
            font=self.font_normal,
            background="#ffe2fa",
        )
        self.tree.tag_configure(
            "WARNING",
            foreground="orange",
            font=self.font_normal,
            background="#43fb65",
        )
        self.tree.tag_configure(
            "ERROR",
            foreground="red",
            font=self.font_bold_normal,
            background="#6970fe",
        )
        self.tree.tag_configure(
            "CRITICAL",
            foreground="red",
            font=self.font_bold_normal,
            background="#0844c5",
        )
        self.tree.tag_configure(
            "TRACE_JUMP",
            foreground="#6a0dad",
            font=self.font_bold_normal,
            background="#f3e8ff",
        )
        self.tree.tag_configure(
            "REBOOT",
            foreground="#7a3b00",
            font=self.font_bold_normal,
            background="#ffe8cc",
        )

        self.tree.bind("<ButtonRelease-1>", self.on_click)
        self.tree.bind("<Double-1>", self.on_double_click)

    def reload_log(self, path: Path) -> None:
        """単一ログファイルを読み込む"""
        logs: LogRows = load_log(path)
        self.rows_raw = logs
        self.rows = summarize(logs)
        self.update_filters()
        self.apply_filter()

    def open_log_file(self) -> None:
        """ファイルダイアログから単一ログを開く"""

        file_path_str: str = filedialog.askopenfilename(
            title="ログファイルを選択",
            initialdir=str(self.log_dir),
            filetypes=[("Log Files", "*.jsonl *.log"), ("All Files", "*.*")],
        )

        if not file_path_str:
            return

        # 🔹 searcher経由で取得（統一）
        logs: list[LogRow] = collect_logs([Path(file_path_str)])

        self.rows_raw = logs
        self.rows = summarize(logs)
        self.update_filters()
        self.apply_filter()

    def open_logs(self) -> None:
        """複数ログを選択して開く"""
        selector = LogFileSelector(self.root, self.log_dir)
        paths: list[Path] | None = selector.show()

        if paths is None:
            return

        # 🔹 データ取得はsearcherに任せる
        logs: LogRows = collect_logs(paths)

        # 🔹 Viewerは表示だけ
        self.rows_raw = logs
        self.rows = summarize(logs)
        self.update_filters()
        self.apply_filter()

    def update_filters(self) -> None:
        """フィルタ候補を更新する"""
        trace_ids: list[str] = sorted(
            {
                self._get_trace_id(row)
                for row in self.rows
                if self._get_trace_id(row)
            }
        )
        types: list[str] = sorted(
            {
                self._get_type(row)
                for row in self.rows
                if self._get_type(row)
            }
        )

        self.trace_dropdown["values"] = [self.TRACE_ALL] + trace_ids
        self.type_dropdown["values"] = [self.TYPE_ALL] + types

        self.trace_var.set(self.TRACE_ALL)
        self.type_var.set(self.TYPE_ALL)

    def reset_filters(self) -> None:
        """フィルタを解除する"""
        self.trace_var.set(self.TRACE_ALL)
        self.type_var.set(self.TYPE_ALL)
        self.apply_filter()

    def apply_filter(self, _event: tk.Event | None = None) -> None:
        """フィルタに応じて表示内容を更新する"""
        trace_filter: str = self.trace_var.get()
        type_filter: str = self.type_var.get()

        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        for index, row in enumerate(self.rows):
            row_trace_id: str = self._get_trace_id(row)
            row_type: str = self._get_type(row)

            if trace_filter != self.TRACE_ALL and row_trace_id != trace_filter:
                continue
            if type_filter != self.TYPE_ALL and row_type != type_filter:
                continue

            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    self._format_local_time(row.get("time")),
                    row_type,
                    row_trace_id,
                    self._get_message(row),
                ),
                tags=(row_type,),
            )

    def _format_local_time(self, value: Any) -> str:
        """UTCをJST表示文字列へ変換する"""
        dt: datetime | None = to_jst_datetime(value)
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt is not None else str(value)

    def _get_type(self, row: LogRow) -> str:
        """type文字列を安全に返す"""
        return str(row.get("type") or row.get("level") or "INFO")

    def _get_message(self, row: LogRow) -> str:
        """message文字列を安全に返す"""
        return str(row.get("message") or row.get("what", {}).get("message", ""))

    def _get_trace_id(self, row: LogRow) -> str:
        """trace_id文字列を安全に返す"""
        return str(row.get("trace_id") or "")

    def on_click(self, event: tk.Event) -> None:
        """シングルクリックで詳細表示"""
        row: dict[str, Any] | None = self._get_row(event)
        if row is None:
            return

        self._cancel_pending_single_click()
        self._single_click_after_id = self.root.after(
            200,
            lambda: self._open_detail(row),
        )

    def on_double_click(self, event: tk.Event) -> None:
        """ダブルクリックでVSCodeを開く"""
        self._cancel_pending_single_click()

        row: dict[str, Any] | None = self._get_row(event)
        if row is None:
            return

        raw_value: Any | None = row.get("raw")
        raw: LogRow = cast(
            LogRow,
            raw_value
            if isinstance(raw_value, dict)
            else row)
        where: LogRow = raw.get("where", {}) if isinstance(raw.get("where"), dict) else {}

        file_path: str = str(where.get("file") or "")
        line_no: int = int(where.get("line") or 1)

        self.open_in_vscode(file_path, line_no)

    def _cancel_pending_single_click(self) -> None:
        """予約済みのシングルクリック処理を取り消す"""
        if self._single_click_after_id is None:
            return

        self.root.after_cancel(self._single_click_after_id)
        self._single_click_after_id = None

    def _get_row(self, event: tk.Event) -> LogRow | None:
        """クリック位置から行データを取得する"""
        row_id: str = self.tree.identify_row(event.y)
        if not row_id:
            return None

        try:
            index = int(row_id)
        except ValueError:
            return None

        if index < 0 or index >= len(self.rows):
            return None

        return self.rows[index]


    def _open_detail(self, row: LogRow) -> None:
        """選択されたログの詳細を表示する"""
        raw_value: Any | None = row.get("raw")
        raw: LogRow = cast(
            LogRow,
            raw_value
            if isinstance(raw_value, dict) else row)

        # =========================
        # 🔹 ウィンドウ
        # =========================
        detail = tk.Toplevel(self.root)
        detail.title("詳細情報")
        detail.geometry("900x650")

        frame = tk.Frame(detail)
        frame.pack(fill=tk.BOTH, expand=True)

        # =========================
        # 🔹 基本情報取得
        # =========================
        level: str = self._get_type(row)
        time_str: str = self._format_local_time(row.get("time"))

        where: LogRow = raw.get("where", {}) if isinstance(raw.get("where"), dict) else {}
        file_path: str = str(where.get("file") or "")
        line_no: str = str(where.get("line") or "")
        function_name: str = str(where.get("function") or "")

        context: LogRow = (
            raw.get("context", {}) if isinstance(raw.get("context"), dict) else {}
        )

        # =========================
        # 🔹 UNIX時間を自動変換
        # =========================
        def format_if_time(key: str, value: Any) -> Any:
            if isinstance(value, (int, float)) and "time" in key:
                try:
                    return self._format_local_time(value)
                except Exception:
                    return value
            return value

        # =========================
        # 🔹 Context整形
        # =========================
        context_lines: list[str] = []

        for k, v in context.items():
            v = format_if_time(k, v)
            context_lines.append(f"{k:<22}: {v}")

        context_text: str = "\n".join(context_lines)

        # =========================
        # 🔹 上部概要（改善版🔥）
        # =========================
        summary_text: str = f"""
            Level : {level}
            Time  : {time_str}

            File  : {file_path}
            Line  : {line_no}
            Func  : {function_name}

            --- Context ---
            {context_text}
            """

        tk.Label(
            frame,
            text=summary_text,
            justify="left",
            font=self.font_normal,
            anchor="w",
        ).pack(fill=tk.X, padx=10, pady=(10, 10))

        # =========================
        # 🔹 VSCodeボタン
        # =========================
        tk.Button(
            frame,
            text="Open in VSCode",
            command=lambda: self.open_in_vscode(
                file_path,
                int(line_no or 1),
            ),
        ).pack(anchor="w", padx=10, pady=(0, 8))

        # =========================
        # 🔹 JSON詳細表示
        # =========================
        text = tk.Text(
            frame,
            wrap="word",
            font=self.font_mono,
        )
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        text.insert("1.0", json.dumps(raw, indent=2, ensure_ascii=False))
        text.config(state="disabled")


    def open_in_vscode(self, file_path: str, line_no: int) -> None:
        """VSCodeで該当ファイルを開く"""
        if not file_path:
            return
        subprocess.run(["code", "-g", f"{file_path}:{line_no}"], check=False)


if __name__ == "__main__":
    root = tk.Tk()
    latest_candidates: list[Path] = sorted(
        list(LOGS_DIR.glob("*.jsonl")) +
        list(LOGS_DIR.glob("*.log"))
    )
    initial_path: Path | None = latest_candidates[-1] if latest_candidates else None
    LogViewer(root, initial_path)
    root.mainloop()
