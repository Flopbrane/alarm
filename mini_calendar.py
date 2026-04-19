# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
# mini calendar module
#########################

# mini_calendar.py
# 汎用ミニカレンダー（単一日付選択用）
# 黒川さんの既存コードを基に、アラームアプリ等で再利用しやすい形に最適化

from __future__ import annotations

import tkinter as tk
from tkinter import Toplevel
import calendar
import re
from pathlib import Path
from datetime import date, datetime
from dataclasses import dataclass


def load_window_position(_window: tk.Misc, _key: str) -> None:
    """ウィンドウ位置復元の互換フック。

    NOTE:
    window_position は現時点では構造エラー回避を優先し、
    mini_calendar.py 内では実処理を持たせない。
    """
    return None


def save_window_position(_window: tk.Misc, _key: str) -> None:
    """ウィンドウ位置保存の互換フック。

    NOTE:
    window_position は現時点では構造エラー回避を優先し、
    mini_calendar.py 内では実処理を持たせない。
    """
    return None


LOG_DATE_PATTERN: re.Pattern[str] = re.compile(r"(?P<date>\d{4}-\d{2}-\d{2})")


def collect_log_dates(log_dir: Path) -> set[date]:
    """ログ/JSONLファイル名に含まれる YYYY-MM-DD を有効日として収集する"""
    dates: set[date] = set()

    for path in log_dir.iterdir():
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".log", ".jsonl"}:
            continue

        match: re.Match[str] | None = LOG_DATE_PATTERN.search(path.name)
        if match is None:
            continue

        try:
            dates.add(datetime.strptime(match.group("date"), "%Y-%m-%d").date())
        except ValueError:
            continue

    return dates


# =========================
# データモデル
# =========================
@dataclass
class DateRange:
    """日付範囲"""
    start: date
    end: date


# =========================
# 単日カレンダー
# =========================
class MiniCalendar:
    """単一日付選択用カレンダー"""
    def __init__(
        self,
        parent: tk.Misc,
        *,
        initial_date: date | None = None,
    ) -> None:
        self.parent: tk.Misc = parent
        self.initial_date: date = initial_date or date.today()

        # 状態
        self.selected_date: date | None = None
        self.result: date | None = None

        # UI
        self.window: Toplevel | None = None
        self.cal_frame: tk.Frame | None = None

        self.year_var: tk.StringVar | None = None
        self.month_var: tk.StringVar | None = None
        self.status_var: tk.StringVar | None = None

    # =========================
    # 公開API
    # =========================
    def show(self) -> date | None:
        """メイン呼び出し"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("日付選択")

        self._build_ui()

        self.parent.wait_window(self.window)
        return self.result

    # =========================
    # UI構築
    # =========================
    def _build_ui(self) -> None:
        assert self.window is not None

        top = tk.Frame(self.window)
        top.pack()

        self.year_var = tk.StringVar(value=str(self.initial_date.year))
        self.month_var = tk.StringVar(value=str(self.initial_date.month))

        tk.Entry(top, textvariable=self.year_var, width=6).pack(side=tk.LEFT)
        tk.Entry(top, textvariable=self.month_var, width=4).pack(side=tk.LEFT)

        tk.Button(top, text="更新", command=self._draw_calendar).pack(side=tk.LEFT)

        self.cal_frame = tk.Frame(self.window)
        self.cal_frame.pack()

        self.status_var = tk.StringVar()
        tk.Label(self.window, textvariable=self.status_var).pack()

        btn_frame = tk.Frame(self.window)
        btn_frame.pack()

        tk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="キャンセル", command=self._on_cancel).pack(
            side=tk.LEFT
        )

        self._draw_calendar()

    # =========================
    # カレンダー描画
    # =========================
    def _draw_calendar(self) -> None:
        if not self.cal_frame or not self.year_var or not self.month_var:
            return

        for w in self.cal_frame.winfo_children():
            w.destroy()

        year = int(self.year_var.get())
        month = int(self.month_var.get())

        calendar.setfirstweekday(calendar.SUNDAY)
        weeks: list[list[int]] = calendar.monthcalendar(year, month)

        for r, week in enumerate(weeks):
            for c, d in enumerate(week):
                if d == 0:
                    tk.Label(self.cal_frame, text=" ").grid(row=r, column=c)
                    continue

                current = date(year, month, d)
                if current == self.initial_date:
                    self.selected_date = current

                fg: str
                bg: str
                fg, bg = self._get_style(current, c)

                tk.Button(
                    self.cal_frame,
                    text=str(d),
                    fg=fg,
                    bg=bg,
                    width=4,
                    command=lambda d=current: self._select_date(d),
                ).grid(row=r, column=c)

    # =========================
    # スタイル
    # =========================
    def _get_style(self, current: date, col: int) -> tuple[str, str]:
        fg = "black"
        bg = "white"

        if self.selected_date == current:
            return "white", "green"

        if current == date.today():
            return "black", "#fff3cd"

        if col == 0:
            return "black", "#ffe6e6"
        if col == 6:
            return "black", "#e6f0ff"

        return fg, bg

    # =========================
    # イベント
    # =========================
    def _select_date(self, d: date) -> None:
        self.selected_date = d
        if self.status_var:
            self.status_var.set(f"選択日: {d.isoformat()}")
        self._draw_calendar()

    def _on_ok(self) -> None:
        if self.selected_date:
            self.result = self.selected_date
        if self.window:
            self.window.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        if self.window:
            self.window.destroy()


# =========================
# 範囲カレンダー
# =========================
class LogDateRangeCalendar:
    """日付範囲選択用カレンダー。開始日と終了日を選択して DateRange を返す。"""
    def __init__(
        self,
        parent: tk.Misc,
        available_dates: set[date],
    ) -> None:
        self.parent: tk.Misc = parent
        self.available_dates: set[date] = available_dates

        self.selected_start: date | None = None
        self.selected_end: date | None = None
        self.result: DateRange | None = None

        self.window: Toplevel | None = None
        self.cal_frame: tk.Frame | None = None

        self.year_var: tk.StringVar | None = None
        self.month_var: tk.StringVar | None = None

    def show(self) -> DateRange | None:
        """選択期間を返す。キャンセルされた場合は None を返す。"""
        self.window = tk.Toplevel(self.parent)
        self.window.title("期間選択")

        self._build_ui()

        self.parent.wait_window(self.window)
        return self.result

    def _build_ui(self) -> None:
        """UI構築"""
        assert self.window is not None

        self.year_var = tk.StringVar(value=str(date.today().year))
        self.month_var = tk.StringVar(value=str(date.today().month))

        top = tk.Frame(self.window)
        top.pack()

        tk.Entry(top, textvariable=self.year_var, width=6).pack(side=tk.LEFT)
        tk.Entry(top, textvariable=self.month_var, width=4).pack(side=tk.LEFT)
        tk.Button(top, text="更新", command=self._draw_calendar).pack(side=tk.LEFT)

        self.cal_frame = tk.Frame(self.window)
        self.cal_frame.pack()

        btn_frame = tk.Frame(self.window)
        btn_frame.pack()

        tk.Button(btn_frame, text="OK", command=self._on_ok).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="キャンセル", command=self._on_cancel).pack(
            side=tk.LEFT
        )

        self._draw_calendar()

    def _draw_calendar(self) -> None:
        """カレンダー描画"""
        if not self.cal_frame or not self.year_var or not self.month_var:
            return

        for w in self.cal_frame.winfo_children():
            w.destroy()

        year = int(self.year_var.get())
        month = int(self.month_var.get())

        weeks: list[list[int]] = calendar.monthcalendar(year, month)

        for r, week in enumerate(weeks):
            for c, d in enumerate(week):
                if d == 0:
                    tk.Label(self.cal_frame, text=" ").grid(row=r, column=c)
                    continue

                current = date(year, month, d)

                bg = "white"
                if self.selected_start == current or self.selected_end == current:
                    bg = "green"
                elif self._in_range(current):
                    bg = "#d9f2d9"
                elif current in self.available_dates:
                    bg = "#e6f7ff"

                tk.Button(
                    self.cal_frame,
                    text=str(d),
                    width=4,
                    bg=bg,
                    command=lambda d=current: self._select_date(d),
                ).grid(row=r, column=c)

    def _in_range(self, d: date) -> bool:
        """選択範囲内か"""
        if self.selected_start and self.selected_end:
            return self.selected_start <= d <= self.selected_end
        return False

    def _select_date(self, d: date) -> None:
        """日付選択。最初のクリックで開始日、次のクリックで終了日を選択する。"""
        if d not in self.available_dates:
            return

        if self.selected_start is None or self.selected_end is not None:
            self.selected_start = d
            self.selected_end = None
        else:
            start: date
            end: date
            start, end = sorted((self.selected_start, d))
            self.selected_start = start
            self.selected_end = end

        self._draw_calendar()

    def _on_ok(self) -> None:
        """OKボタン。開始日と終了日が選択されていれば result にセットしてウィンドウを閉じる。"""
        if self.selected_start and self.selected_end:
            self.result = DateRange(self.selected_start, self.selected_end)
        if self.window:
            self.window.destroy()

    def _on_cancel(self) -> None:
        """キャンセルボタン。選択を破棄してウィンドウを閉じる。"""
        self.result = None
        if self.window:
            self.window.destroy()


# # =============================
# # 🕒 TimePicker クラス（時刻ピッカー）
# # =============================
# # クリックで時と分を選択して "HH:MM" を返す汎用モジュール
# class TimePicker:
#     """
#     シンプルな時刻選択ダイアログ。
#     00〜23時、00〜59分を選択して "HH:MM" を返す。


#     例：
#     tp = TimePicker(initial_time="07:30")
#     result = tp.show()
#     """
#     def __init__(
#         self,
#         parent: tk.Misc,
#         initial_time: str = "07:00",
#         window_key: str | None = None,
#     ) -> None:
#         self.parent: tk.Misc = parent
#         try:
#             h: int
#             m: int
#             h, m = map(int, initial_time.split(":"))
#         except Exception:
#             now: datetime = datetime.now()
#             # 秒があれば切り上げて次の分
#             base: datetime = now.replace(second=0, microsecond=0)
#             if now.second or now.microsecond:
#                 base = base + timedelta(minutes=1)
#             h, m = base.hour, base.minute

#         self.hour: int = h
#         self.minute: int = m
#         self.selected_time: str | None = None
#         self.window_key: str | None = window_key
#         self.master: Toplevel | None = None
#         self.hour_var: tk.StringVar | None = None
#         self.minute_var: tk.StringVar | None = None

#     # -----------------------------
#     def show(self) -> str | None:
#         """メイン呼び出し"""
#         self._build_window()
#         if self.master is not None:
#             self.master.wait_window()
#         return self.selected_time

#     # -----------------------------
#     def _build_window(self) -> None:
#         self.master = Toplevel(self.parent)
#         self.master.title("時刻を選択")
#         self.master.geometry("220x180")
#         self.master.resizable(False, False)
#         if self.window_key:
#             try:
#                 load_window_position(self.master, self.window_key)
#             except Exception:
#                 pass

#         frame = tk.Frame(self.master)
#         frame.pack(pady=20)

#         # 時の選択
#         tk.Label(frame, text="時：").grid(row=0, column=0)
#         self.hour_var = tk.StringVar(value=f"{self.hour:02d}")
#         hour_box = ttk.Combobox(frame,
#         textvariable=self.hour_var,
#         values=[f"{i:02d}" for i in range(24)],
#         width=5,
#         state="readonly"
#         )
#         hour_box.grid(row=0, column=1, padx=5)

#         # 分の選択
#         tk.Label(frame, text="分：").grid(row=1, column=0)
#         self.minute_var = tk.StringVar(value=f"{self.minute:02d}")
#         minute_box = ttk.Combobox(frame,
#         textvariable=self.minute_var,
#         values=[f"{i:02d}" for i in range(60)],
#         width=5,
#         state="readonly"
#         )
#         minute_box.grid(row=1, column=1, padx=5)

#         # 決定ボタン
#         ttk.Button(self.master, text="OK", width=12,
#         command=self._commit
#         ).pack(pady=15)

#     # -----------------------------
#     def _commit(self) -> None:
#         if self.hour_var is None or self.minute_var is None:
#             return
#         h: str = self.hour_var.get()
#         m: str = self.minute_var.get()
#         self.selected_time = f"{h}:{m}"
#         if self.window_key and self.master is not None:
#             try:
#                 save_window_position(self.master, self.window_key)
#             except Exception:
#                 pass
#         if self.master is not None:
#             self.master.destroy()
