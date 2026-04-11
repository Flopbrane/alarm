# -*- coding: utf-8 -*-
"""ログファイルを読み込んで表示するシンプルなGUIアプリ"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from __future__ import annotations

# 標準ライブラリ
from datetime import datetime, date
import json
import tkinter as tk
from tkinter import ttk, filedialog
import subprocess
from pathlib import Path
from typing import Any

# 自作モジュール
from env_paths import LOGS_DIR  # ← ここ重要
from logs.log_searcher import load_logs, summarize
from logs.time_utils import to_jst_datetime
from mini_calendar import collect_log_dates, LogDateRangeCalendar, DateRange

# ============================
# LogViewer本体
# ============================
class LogViewer:
    """ログファイルを読み込んで表示するシンプルなGUIアプリ"""
    TRACE_ALL = "trace.id_ALL"
    TYPE_ALL = "type_ALL"

    def __init__(self, parent: tk.Tk, path: Path) -> None:
        self.root: tk.Tk = parent
        self.root.title("Log Viewer")
        self.root.geometry("1420x500+100+200") #画面サイズ"幅x高さ+X座標(画面左端から)+Y座標(画面上端から)"
        self._single_click_after_id: str | None = None
        self.log_dir: Path = LOGS_DIR
        self.trace_var = tk.StringVar(value=self.TRACE_ALL)
        self.type_var = tk.StringVar(value=self.TYPE_ALL)
        # =========================
        # 🔹 メニューバー
        # =========================
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)

        file_menu.add_command(label="過去ログを開く", command=self.open_log_file)
        file_menu.add_separator()
        file_menu.add_command(label="日付範囲で開く", command=self.open_date_range)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self.root.quit)
        # =========================
        # フォント定義（ここが重要🔥）
        # =========================
        self.font_title = ("Yu Gothic UI", 12, "bold")
        self.font_normal = ("Yu Gothic UI", 10)
        self.font_mono = ("Cascadia Code", 10)
        # =========================
        # Treeview(一覧表示)の設定
        # =========================
        self.tree = ttk.Treeview(
            self.root, columns=("time", "type", "trace_id", "message"), show="headings"
        )
        # タグごとに色を設定
        self.tree.tag_configure("INFO",
                                foreground="black",
                                font=self.font_normal,
                                background="#ffffff")
        self.tree.tag_configure("ERROR",
                                foreground="red",
                                font=self.font_normal,
                                background="#3477f4")
        self.tree.tag_configure("CRITICAL",
                                foreground="red",
                                font=self.font_normal,
                                background="#3a34f0")
        self.tree.tag_configure("WARNING",
                                foreground="orange",
                                font=self.font_normal,
                                background="#5e34f4")
        self.tree.tag_configure("TRACE_JUMP",
                                foreground="yellow",
                                font=self.font_normal,
                                background="#b338fb")
        self.tree.tag_configure("REBOOT",
                                foreground="purple",
                                font=self.font_normal,
                                background="#f4a234")

        for col in ("time", "type", "trace_id", "message"):
            self.tree.heading(col, text=col.upper())

        filter_frame = tk.Frame(self.root)
        filter_frame.pack(fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.rows_raw: list[dict[str, Any]] = load_logs(path)
        self.rows: list[dict[str, Any]] = summarize(self.rows_raw)

        for i, row in enumerate(self.rows):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    self._format_display_time(row.get("time")),
                    row["type"],
                    row["trace_id"],
                    self.format_event(row),  # ← ★これも変更（イベントの内容をわかりやすく表示する）
                ),
                tags=(row["type"],),
            )

        self.tree.bind("<ButtonRelease-1>", self.on_click)
        self.tree.bind("<Double-1>", self.on_double_click)

        # =========================
        # 🔹 trace_idフィルタUI
        # =========================
        filter_frame = tk.Frame(self.root)
        filter_frame.pack(fill=tk.X)

        # trace_id一覧取得
        trace_ids: list[Any] = sorted({row["trace_id"] for row in self.rows})

        self.trace_var = tk.StringVar(value=self.TRACE_ALL)

        self.trace_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.trace_var,
            values=[self.TRACE_ALL] + trace_ids,
            state="readonly",
        )
        self.trace_dropdown.pack(side=tk.LEFT)

        self.trace_dropdown.bind("<<ComboboxSelected>>", self.apply_filter)

        # =========================
        # 🔹 typeフィルタUI
        # =========================
        types: list[Any] = sorted({row["type"] for row in self.rows})

        self.type_var = tk.StringVar(value=self.TYPE_ALL)

        self.type_dropdown = ttk.Combobox(
            filter_frame,
            textvariable=self.type_var,
            values=[self.TYPE_ALL] + types,
            state="readonly",
        )
        self.type_dropdown.pack(side=tk.LEFT)

        self.type_dropdown.bind("<<ComboboxSelected>>", self.apply_filter)
        # =========================
        # 🔹 リセットボタン
        # =========================
        reset_button = tk.Button(filter_frame, text="Reset", command=self.reset_filters)
        reset_button.pack(side=tk.LEFT, padx=5)

        # フィルタの初期化
        self.apply_filter()  # 初期表示のフィルタ適用

    # ============================
    # 🔹 ログファイルオープン
    # ============================
    def open_log_file(self) -> None:
        """ログファイルを選択して再読み込み"""
        file_path: str = filedialog.askopenfilename(
            title="ログファイルを選択",
            filetypes=[("Log Files", "*.jsonl *.log"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        self.reload_logs(Path(file_path))

    # ============================
    # 🔹 ログ内容表示(info情報も含む)
    # ============================
    def format_raw_log(self, log: dict[str, Any]) -> str:
        """生ログの内容をわかりやすく表示する（将来の拡張用）"""
        return log.get("what", {}).get("message", "")

    # ============================
    # 🔹 ログディレクトリオープン
    # ============================
    def open_date_range(self) -> None:
        """ログファイルが存在する日だけを選択できる日付範囲カレンダーを開く"""

        # -----------------------------
        # 日付取得
        # -----------------------------
        available_dates: set[date] = collect_log_dates(LOGS_DIR)

        # -----------------------------
        # カレンダー表示
        # -----------------------------
        cal: LogDateRangeCalendar = LogDateRangeCalendar(self.root, available_dates)

        result: DateRange | None = cal.show()

        if result is not None:
            start_date: date = result.start
            end_date: date = result.end
        else:
            return

        start: str = start_date.strftime("%Y-%m-%d")
        end: str = end_date.strftime("%Y-%m-%d")

        # -----------------------------
        # ファイル抽出
        # -----------------------------
        paths: list[Path] = [
            p
            for p in LOGS_DIR.iterdir()
            if p.is_file() and len(p.stem) >= 10 and start <= p.stem[-10:] <= end
        ]

        # -----------------------------
        # ログ読み込み
        # -----------------------------
        logs: list[dict[str, Any]] = self.load_logs_multi(paths)

        # -----------------------------
        # ソート（安全化）
        # -----------------------------
        logs.sort(key=lambda x: str(x.get("time", "")))

        # -----------------------------
        # 要約（型保証）
        # -----------------------------
        summarized: list[dict[str, Any]] = summarize(logs)

        # -----------------------------
        # 反映
        # -----------------------------
        self.rows = summarized
        self.apply_filter()

    # ============================
    # 🔹 ログ詳細表示(イベント内容)
    # ============================
    def _get_type(self, row: dict[str, Any]) -> str:
        type_value: str = str(row.get("type") or row.get("level") or "INFO")
        return type_value

    def _get_message(self, row: dict[str, Any]) -> str:
        message_value: str = str(row.get("message") or row.get("what", {}).get("message", ""))
        return message_value

    def _get_trace_id(self, row: dict[str, Any]) -> str:
        trace_value: str = str(row.get("trace_id") or "")
        return trace_value

    # ============================
    # 🔹 ログ再読み込み
    # ============================
    def reload_logs(self, path: Path) -> None:
        """ログを再読み込みして画面更新"""
        logs: list[dict[str, Any]] = load_logs(path)
        self.rows = summarize(logs)

        # Treeクリア
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 再描画
        for i, row in enumerate(self.rows):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    self._format_display_time(row.get("time")),
                    self._get_type(row),
                    self._get_trace_id(row),
                    self._get_message(row),
                ),
                tags=(self._get_type(row),),
            )

        # フィルタも更新
        self.update_filters()

    # ============================
    # 🔹 複数ログ読み込み
    # ============================
    def load_logs_multi(self, paths: list[Path]) -> list[dict[str, Any]]:
        """複数のログファイルを読み込む（将来の拡張用）"""
        all_logs: list[dict[str, Any]] = []
        for path in paths:
            all_logs.extend(load_logs(path))
        return all_logs

    def safe_sort(self, logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """ログを安全にソートする（timeキーがない場合も考慮）"""
        return sorted(
            logs,
            key=lambda x: x.get("time", "")
        )

    def filter_by_date(self, paths: list[Path], start: str, end: str) -> list[Path]:
        """ファイル名の日付部分でログファイルをフィルタリングする（将来の拡張用）"""
        return [
            p for p in paths
            if start <= p.stem[-10:] <= end
        ]

    def filter_by_time(self,
                       logs: list[dict[str, Any]],
                       start: str,
                       end: str) -> list[dict[str, Any]]:
        """ログのtimeキーでフィルタリングする（将来の拡張用）"""
        return [
            log for log in logs
            if start <= log.get("time", "") <= end
        ]

    # def collect_log_dates(self, logs_directory: Path) -> set[date]:
    #     """ログディレクトリから利用可能な日付を抽出する"""
    #     available_dates: set[date] = set()
    #     for log_file in logs_directory.glob("*.jsonl"):
    #         try:
    #             logs: list[dict[str, Any]] = load_logs(log_file)
    #             for log in logs:
    #                 dt: datetime | None = to_jst_datetime(log.get("time"))
    #                 if dt is not None:
    #                     available_dates.add(dt.date())
    #         except (json.JSONDecodeError, OSError):
    #             pass
    #     return available_dates

    # ============================
    # 🔹 フィルタ更新
    # ============================
    def update_filters(self) -> None:
        """フィルタの選択肢をログ内容に合わせて更新する"""
        trace_ids: list[Any] = sorted({self._get_trace_id(row) for row in self.rows})
        types: list[Any] = sorted({self._get_type(row) for row in self.rows})

        self.trace_var.set(self.TRACE_ALL)
        self.type_var.set(self.TYPE_ALL)

        # trace_idフィルタ更新
        self.trace_dropdown.config(values=[self.TRACE_ALL] + trace_ids)

        # typeフィルタ更新
        self.type_dropdown.config(values=[self.TYPE_ALL] + types)

    # ============================
    # 🔹 リセット処理
    # ============================
    def reset_filters(self) -> None:
        """フィルタをリセットする"""
        self.trace_var.set(self.TRACE_ALL)
        self.type_var.set(self.TYPE_ALL)
        self.apply_filter()

    # ============================
    # 🔹 フィルタ処理
    # ============================
    def apply_filter(self, _event: tk.Event | None = None) -> None:
        """ドロップダウンの選択に応じて表示をフィルタリングする"""
        trace_filter: str = self.trace_var.get()
        type_filter: str = self.type_var.get()

        # 🔥 ここ追加
        if type_filter == self.TYPE_ALL:
            self.rows: list[dict[str, Any]] = self.rows_raw  # ← 生ログ
        else:
            self.rows: list[dict[str, Any]] = self.rows  # ← イベント

        # Treeをクリア
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 再表示
        for i, row in enumerate(self.rows):
            if trace_filter != self.TRACE_ALL and self._get_trace_id(row) != trace_filter:
                continue

            if type_filter == self.TYPE_ALL:
                message: str = self._get_message(row)
                type_: str = self._get_type(row)
                trace_id: str = self._get_trace_id(row)
                time: str = self._format_display_time(row.get("time"))
            else:
                message: str = self._get_message(row)
                type_: str = self._get_type(row)
                trace_id: str = self._get_trace_id(row)
                time: str = self._format_display_time(row.get("time"))

            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    time,
                    type_,
                    trace_id,
                    message,
                ),
                tags=(type_,),
            )

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
            return f"ERROR: {event.get('message', '')}"

        return event.get("message", "")

    def _format_display_time(self, value: Any) -> str:
        """保存はUTC、表示はJSTへ変換する"""
        dt: datetime | None = to_jst_datetime(value)
        if dt is None:
            return str(value) if value is not None else ""
        return dt.strftime("%Y-%m-%d %H:%M:%S JST")

    # ============================
    # 🔹 その他のイベント処理
    # ============================
    # ここに他のイベント処理関数を追加していく
    def open_in_vscode(self, file: str, line: int) -> None:
        """VSCodeで該当行を開く"""
        if not file:
            return
        subprocess.run(["code", "-g", f"{file}:{line}"], check=False)

    def _get_row_from_event(self, event: tk.Event) -> dict[str, Any] | None:
        """クリック位置から LogEvent を取得する"""
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

    def _open_detail(self, row: dict[str, Any]) -> None:
        """選択されたログの詳細を表示する"""
        raw: dict[str, Any] = row.get("raw") or row

        detail = tk.Toplevel(self.root)
        detail.title("Detail")

        frame = tk.Frame(detail)
        frame.pack(fill=tk.BOTH, expand=True)

        # ===== 上部：要約 =====
        summary = tk.Label(
            frame,
            text=f"{self._get_type(row)} | {self._format_display_time(row.get('time'))}",
            font=self.font_title,
        )
        summary.pack(anchor="w")

        # ===== where情報 =====
        where: dict[str, Any] = raw.get("where", {})

        where_text: str = (
            f"{where.get('file')}:{where.get('line')}\n"
            f"{where.get('function')}"
        )

        where_label = tk.Label(frame, text=where_text, justify="left", font=self.font_normal)
        where_label.pack(anchor="w")

        # ===== context =====
        context: dict[str, Any] = raw.get("context", {})
        context_label = tk.Label(
            frame,
            text=f"Context: {context}",
            justify="left",
            font=self.font_normal,
        )
        context_label.pack(anchor="w")

        btn = tk.Button(
            frame,
            text="Open in VSCode",
            command=lambda: self.open_in_vscode(
                str(where.get("file", "")),
                int(where.get("line", 1) or 1),
            ),
        )
        btn.pack()

        # ===== JSON =====
        text = tk.Text(
            frame,
            wrap="word",
            font=self.font_mono,  # ←コード用フォントを指定
            )
        text.pack(fill=tk.BOTH, expand=True)

        text.insert("1.0", json.dumps(raw, indent=2, ensure_ascii=False))

    def _cancel_pending_single_click(self) -> None:
        """ダブルクリック時にシングルクリック処理の予約を取り消す"""
        if self._single_click_after_id is None:
            return

        self.root.after_cancel(self._single_click_after_id)
        self._single_click_after_id = None

    # ============================
    # 🔹 行クリックイベント
    # ============================
    def on_click(self, event: tk.Event) -> None:
        """行がクリックされたときに詳細ウィンドウを表示する"""
        self._cancel_pending_single_click()
        row: dict[str, Any] | None = self._get_row_from_event(event)
        if row is None:
            return

        self._single_click_after_id = self.root.after(
            250,
            lambda: self._open_detail(row),
        )

    def on_double_click(self, event: tk.Event) -> None:
        """行をダブルクリックしたときに VSCode でログ発生箇所を開く"""
        self._cancel_pending_single_click()
        row: dict[str, Any] | None = self._get_row_from_event(event)
        if row is None:
            return

        raw: dict[str, Any] = row.get("raw", {})
        where: dict[str, Any] = raw.get("where", {})
        self.open_in_vscode(
            str(where.get("file", "")),
            int(where.get("line", 1) or 1),
        )


if __name__ == "__main__":
    root = tk.Tk()
    log_dir: Path = LOGS_DIR
    candidates: list[Path] = [
        p for p in log_dir.iterdir() if p.suffix in (".jsonl", ".log")
    ]
    latest: Path = max(candidates, key=lambda p: p.stat().st_mtime)
    LogViewer(root, latest)
    root.mainloop()
