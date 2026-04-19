# -*- coding: utf-8 -*-
# pylint: disable=W0718
"""ログ表示GUI（安定版）"""
#########################
# Author: F.Kurokawa
# Description:
# log_viewer
#########################

from __future__ import annotations

from datetime import datetime, timezone
import ast
import json
import subprocess
import tkinter as tk
import re
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Any, Final, Union


from logs.log_paths import LOGS_DIR
from logs.log_searcher import summarize, collect_logs
from logs.log_storage import load_log
from logs.multi_info_logger import AppLogger
from logs.time_utils import to_jst_datetime, to_utc_datetime
from logs.log_types import Event, LogDict, LogWhere
from logs.log_validator import validate_log
from logs.display_formatter import LogRenderer
from logs.log_app import get_logger

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
        # 🔥 Eventベースに変更
        self.rows: list[Event] = []
        self._single_click_after_id: str | None = None
        self.base_utc_dt: datetime = datetime.now(timezone.utc) # UTCで運用
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
        self.search_var = tk.StringVar()

        self.logger: AppLogger = get_logger()
        # 画像描画
        self._build_ui()

        if initial_log_path is not None:
            self.reload_log(initial_log_path)

    # =======================
    # 内部の比較は、全てUTCで運用
    # =======================
    def to_utc_search_dt(self, dt: datetime | None) -> datetime | None:
        """内部日時は全てUTCで運用するための変換関数(一覧はJST表示)"""
        if dt is None:
            return None

        # 🔹 timeのみ（1900年）対応
        if dt.year == 1900:
            return datetime.combine(
                self.base_utc_dt.date(),
                dt.time(),
                tzinfo=timezone.utc,
            )

        # 🔹 naive → UTC
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    def format_time(self, dt: datetime) -> str:
        """表示フォーマット修正"""
        logger: AppLogger = get_logger()

        if logger.config.time_precision == "second":
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")

    # =======================
    # UI構築(メイン・ウインド)
    # =======================
    def _build_ui(self) -> None:
        """UIを構築する"""

        # =========================
        # 🔹 上部ボタン
        # =========================
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=8, pady=8)

        tk.Button(top_frame, text="単一ログを開く", command=self.open_log_file).pack(side=tk.LEFT)
        tk.Button(top_frame, text="複数ログを開く", command=self.open_logs).pack(side=tk.LEFT, padx=8)
        tk.Button(top_frame, text="フィルタ解除", command=self.reset_filters).pack(side=tk.LEFT)

        # =========================
        # 🔹 フィルタ
        # =========================
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

        tk.Label(filter_frame, text="SEARCH").pack(side=tk.LEFT)
        tk.Entry(
            filter_frame,
            textvariable=self.search_var,
            width=30,
        ).pack(side=tk.LEFT, padx=(4, 12))

        tk.Button(filter_frame, text="検索", command=self.apply_filter).pack(side=tk.LEFT)

        # =========================
        # 🔥 Tree専用フレーム（重要）
        # =========================
        tree_frame = tk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # 🔹 Scrollbar
        scrollbar = tk.Scrollbar(tree_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        # 🔹 Treeview
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("type", "time", "trace_id", "message"),
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        self.tree.pack(fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.tree.yview)  # type: ignore[arg-type]

        # =========================
        # 🔹 カラム設定
        # =========================
        self.tree.heading("type", text="TYPE")
        self.tree.heading("time", text="TIME")
        self.tree.heading("trace_id", text="TRACE_ID")
        self.tree.heading("message", text="MESSAGE")

        self.tree.column("type", width=120, anchor="w")
        self.tree.column("time", width=180, anchor="w")
        self.tree.column("trace_id", width=250, anchor="w")
        self.tree.column("message", width=640, anchor="w")
        # 通常（INFO）
        self.tree.tag_configure(
            "INFO",
            foreground="#222222",
            font=self.font_normal,
            background="#ffffff",
        )

        # WARNING（注意）
        self.tree.tag_configure(
            "WARNING",
            foreground="#b26a00",
            font=self.font_normal,
            background="#fff4cc",
        )

        # ERROR（エラー）
        self.tree.tag_configure(
            "ERROR",
            foreground="#b00020",
            font=self.font_bold_normal,
            background="#ffe5e5",
        )

        # CRITICAL（致命）
        self.tree.tag_configure(
            "CRITICAL",
            foreground="#ffffff",
            font=self.font_bold_normal,
            background="#d32f2f",
        )

        # REPEAT_ERROR（繰り返しエラー）
        self.tree.tag_configure(
            "REPEAT_ERROR",
            foreground="#ffe0b2",
            font=self.font_bold_normal,
            background="#e65100",  # オレンジ強め🔥
        )

        # TRACE_JUMP（分析系）
        self.tree.tag_configure(
            "TRACE_JUMP",
            foreground="#5e35b1",
            font=self.font_normal,
            background="#f3e8ff",
        )

        # REBOOT（システム系）
        self.tree.tag_configure(
            "REBOOT",
            foreground="#6d4c41",
            font=self.font_normal,
            background="#efebe9",
        )

        self.tree.bind("<ButtonRelease-1>", self.on_click)
        self.tree.bind("<Double-1>", self.on_double_click)

    def reload_log(self, path: Path) -> None:
        """単一ログファイルを再読み込み"""

        # ① 生ログ（dict）
        raw_logs: list[dict[str, Any]] = load_log(path)

        # 🔥 ここが重要
        safe_logs: list[LogDict] = []
        for raw in raw_logs:
            log: LogDict | None = validate_log(raw)
            if log is not None:
                safe_logs.append(log)

        # Event化
        events: list[Event] = summarize(safe_logs)

        # ③ Viewerにセット
        self.rows = events

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
        logs: list[LogDict] = collect_logs([Path(file_path_str)])

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
        logs: list[LogDict] = collect_logs(paths)

        # 🔹 Viewerは表示だけ
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

    def parse_flexible_datetime(self, text: str) -> datetime | None:
        """検索テキストに柔軟性をもたせる"""
        text = text.strip()

        if not text:
            return None

        # 🔹 ISO形式（最優先）
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass

        # 🔹 YYYYMMDD
        if re.fullmatch(r"\d{8}", text):
            try:
                return datetime.strptime(text, "%Y%m%d")
            except ValueError:
                return None

        # 🔹 HH:MM
        if re.fullmatch(r"\d{1,2}:\d{1,2}", text):
            try:
                return datetime.strptime(text, "%H:%M")
            except ValueError:
                return None

        # 🔹 HHMM（例：930 → 09:30）
        if re.fullmatch(r"\d{3,4}", text):
            try:
                return datetime.strptime(text.zfill(4), "%H%M")
            except ValueError:
                return None

            return None

    def parse_range(self, text: str) -> tuple[None, None] | tuple[datetime | None, datetime | None]:
        """日時範囲入力を分離して、UTC開始日時、UTC終了日時を返す"""

        if " - " not in text:
            return None, None
        start_str: str
        end_str: str
        start_str, end_str = text.split(" - ")

        start: datetime | None = self.parse_flexible_datetime(start_str)
        start_utc: datetime | None = self.to_utc_search_dt(start)
        end: datetime | None = self.parse_flexible_datetime(end_str)
        end_utc: datetime | None = self.to_utc_search_dt(end)
        return start_utc, end_utc

    def apply_filter(self, _event: tk.Event | None = None) -> None:
        """フィルタに応じて表示内容を更新する"""

        trace_filter: str = self.trace_var.get()
        type_filter: str = self.type_var.get()
        search_text: str = self.search_var.get().strip().lower()

        # 🔹 画面クリア
        for item_id in self.tree.get_children():
            self.tree.delete(item_id)

        # 🔹 範囲検索準備
        start_utc_dt: datetime | None = None
        end_utc_dt: datetime | None = None

        if " - " in search_text:
            try:
                start_utc_dt, end_utc_dt = self.parse_range(search_text)
            except Exception:
                pass

        if self.rows:
            base: datetime | None = to_utc_datetime(self.rows[0].time)
            self.base_utc_dt = base if base else datetime.now(timezone.utc)

        if start_utc_dt and end_utc_dt and start_utc_dt.year == 1900:
            start_utc_dt = datetime.combine(self.base_utc_dt.date(), start_utc_dt.time())
            end_utc_dt = datetime.combine(self.base_utc_dt.date(), end_utc_dt.time())

        # 🔹 メインループ
        for index, row in enumerate(self.rows):

            row_trace_id: str = self._get_trace_id(row)
            row_type: str = self._get_type(row)

            # 🔹 TRACEフィルタ
            if trace_filter != self.TRACE_ALL and row_trace_id != trace_filter:
                continue

            # 🔹 TYPEフィルタ
            if type_filter != self.TYPE_ALL and row_type != type_filter:
                continue

            # 🔹 時刻（内部変換でUTC基準に統一、表示はJST）
            row_dt: datetime | None = self.parse_flexible_datetime(row.time)

            # 🔹 -----範囲検索-----
            # pylint: disable=C0325
            if start_utc_dt and end_utc_dt:
                if row_dt is None or not (start_utc_dt <= row_dt <= end_utc_dt):
                    continue
            # pylint: enable=C0325

            # 🔹 -----通常検索-----
            elif search_text:
                message: str = self._get_message(row).lower()
                trace_id: str = row_trace_id.lower()
                utc_time: str = str(row.time).lower()
                jst_time: str = self._format_local_time(row.time).lower()

                if (
                    search_text not in message
                    and search_text not in trace_id
                    and search_text not in utc_time
                    and search_text not in jst_time
                ):
                    continue

            # 🔹 表示
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    row_type,
                    self._format_local_time(row.time),
                    row_trace_id,
                    self._get_message(row),
                ),
                tags=(row_type,),
            )

    def _format_local_time(self, value: Any) -> str:
        """UTCをJST表示文字列へ変換する"""
        dt: datetime | None = to_jst_datetime(value)
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt is not None else str(value)

    def _get_type(self, row: Event) -> str:
        """type文字列を安全に返す"""
        if row.type is not None:
            return row.type.name  # ← Enum → str

        return row.level.name  # ← Enum → str

    def _get_message(self, row: Event) -> str:
        """message文字列を安全に返す"""
        return str(row.message)

    def _get_trace_id(self, row: Event) -> str:
        """trace_id文字列を安全に返す"""
        return str(row.trace_id or "")

    def on_click(self, event: tk.Event) -> None:
        """シングルクリックで詳細表示"""
        row: Event | None = self._get_row(event)
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

        row: Event | None = self._get_row(event)
        if row is None:
            return

        # 🔥 Event → raw → where
        raw: LogDict = row.raw
        where: LogWhere = raw.get("where", {})

        file_path: str = str(where.get("file", ""))
        line_no: int = int(where.get("line", 1))

        self.open_in_vscode(file_path, line_no)

    def _cancel_pending_single_click(self) -> None:
        """予約済みのシングルクリック処理を取り消す"""
        if self._single_click_after_id is None:
            return

        self.root.after_cancel(self._single_click_after_id)
        self._single_click_after_id = None

    def _get_row(self, event: tk.Event) -> Event | None:
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

    def extract_source_file(self, msg: str) -> tuple[str | None, int]:
        """messageから、filenameを抽出する"""
        rest: str
        try:
            # ① 分割
            if "→" in msg:
                _, rest = msg.split("→", 1)
            elif "->" in msg:
                _, rest = msg.split("->", 1)
            else:
                return None, 1

            text: str = rest.strip()

            # ② Python辞書として評価（安全）
            data: dict[str, Any] = ast.literal_eval(text)

            # ③ where取得
            where: LogWhere = data.get("where", {})

            file_path: str | None = where.get("file")
            line_no: int = where.get("line", 1)

            return file_path, int(line_no)

        except Exception as e:
            print(f"extract error: {e}")  # デバッグ🔥
            return None, 1

    # ===============================
    # 🔹 詳細ウィンドウ表示
    # ===============================
    def _open_detail(self, row: Event) -> None:
        """選択されたログの詳細を表示する"""
        raw: LogDict = row.raw
        renderer = LogRenderer()
        # =========================
        # 🔹 ウィンドウ
        # =========================
        detail = tk.Toplevel(self.root)
        detail.title("詳細情報")
        detail.geometry("900x1200")

        frame = tk.Frame(detail)
        frame.pack(fill=tk.BOTH, expand=True)

        # =========================
        # 🔹 基本情報
        # =========================
        where: LogWhere = raw.get("where", {})
        file_path: str = str(where.get("file", ""))
        line_no: int = int(where.get("line", 1) or 1)
        # =========================
        # 🔹 上部（色付き表示）
        # =========================
        parts: list[tuple[str, str]] = renderer.build_summary_parts(row)

        for text, color in parts:
            if not text:
                tk.Label(frame, text="").pack(anchor="w")
                continue

            tk.Label(
                frame,
                text=text,
                fg=color or "#000000",  # ← 保険🔥
                justify="left",
                font=self.font_mono,
                anchor="w",
            ).pack(anchor="w", padx=10)

        tk.Frame(frame, height=2, bg="#ccc").pack(fill="x", padx=10, pady=5)
        # =========================
        # 🔹 VSCodeボタン
        # =========================
        # ======ボタン専用フレーム====
        btn_frame = tk.Frame(frame)
        btn_frame.pack(anchor="w", padx=10, pady=(0, 8))
        message = str(raw.get("what", {}).get("message", ""))

        # 🔹 Logger（ログを書いた場所）
        tk.Button(
            btn_frame,
            text="Open Logger(VSCode)",
            fg="#0066cc",
            cursor="hand2",
            width=20,
            command=lambda f=file_path, line=line_no: self.open_in_vscode(f, line),
        ).pack(side=tk.LEFT, padx=5)

        # 🔹 Source（実際の原因）
        src_file: str | None
        src_line: int
        src_file, src_line = self.extract_source_file(message)

        if src_file:
            tk.Button(
                btn_frame,
                text="Open Source(VSCode)",
                cursor="hand2",
                width=20,
                command=lambda f=src_file, line=src_line: self.open_in_vscode(f, line),
            ).pack(side=tk.LEFT, padx=(0, 10))
        # =========================
        # 🔹 RAW
        # =========================
        display_raw: dict[str, Any] = renderer.build_raw(row)

        text_widget = tk.Text(
            frame,
            wrap="word",
            font=self.font_mono,
        )
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text_widget.insert("1.0", "=== RAW DATA ===\n\n")
        text_widget.insert("end", json.dumps(display_raw, indent=2, ensure_ascii=False))
        text_widget.config(state="disabled")

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
