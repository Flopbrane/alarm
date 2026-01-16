# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
# mini carendear module
#########################

# mini_calendar.py
# 汎用ミニカレンダー（単一日付選択用）
# 黒川さんの既存コードを基に、アラームアプリ等で再利用しやすい形に最適化

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import Toplevel
import calendar
from datetime import datetime, date, timedelta
import jpholiday
from utils import load_window_position, save_window_position


class MiniCalendar:
    """
    単一の日付を "YYYY-MM-DD" 形式で返す簡易ミニカレンダーダイアログ。

    使用例：
        selected = MiniCalendar().show()
        print(selected)   # "2025-03-01" など
    """

    def __init__(self, parent, initial_date=None, window_key: str | None = None):
        self.parent = parent
        self.initial_date = (
            datetime.strptime(initial_date, "%Y-%m-%d")
            if isinstance(initial_date, str)
            else datetime.now()
        )
        self.selected_date = None
        self.window_key = window_key

    # -----------------------------
    # メイン呼び出し
    # -----------------------------
    def show(self):
        """メイン呼び出し"""
        self._build_window()
        self.master.wait_window()  # ウインドウが閉じるまで待機
        return self.selected_date

    # -----------------------------
    # GUI 構築
    # -----------------------------
    def _build_window(self):
        self.master = Toplevel(self.parent)
        self.master.title("日付選択")
        self.master.geometry("305x305")
        self.master.resizable(True, True)
        if self.window_key:
            try:
                load_window_position(self.master, self.window_key)
            except Exception:
                pass

        # 年・月
        self.year_var = tk.IntVar(value=self.initial_date.year)
        self.month_var = tk.IntVar(value=self.initial_date.month)
        self.month_var.trace_add("write", lambda *args: self._draw_calendar())

        # 上部エリア
        top = tk.Frame(self.master)
        top.pack(pady=5)

        tk.Entry(top, textvariable=self.year_var, width=5).grid(row=0, column=0)
        tk.Label(top, text="年").grid(row=0, column=1)

        months = [i for i in range(1, 13)]
        tk.OptionMenu(top, self.month_var, *months).grid(row=0, column=2)
        tk.Label(top, text="月").grid(row=0, column=3)

        # カレンダー表示領域
        self.cal_frame = tk.Frame(self.master)
        self.cal_frame.pack(pady=10)

        self._draw_calendar()

    # -----------------------------
    # カレンダー描画
    # -----------------------------
    def _draw_calendar(self):
        for w in self.cal_frame.winfo_children():
            w.destroy()

        year = self.year_var.get()
        month = self.month_var.get()

        # 曜日ラベル
        days = ["日", "月", "火", "水", "木", "金", "土"]
        for i, d in enumerate(days):
            tk.Label(self.cal_frame, text=d).grid(row=0, column=i)

        # カレンダー計算
        calendar.setfirstweekday(calendar.SUNDAY)
        month_days = calendar.monthcalendar(year, month)
        today = datetime.now().day
        is_current_month = (year == datetime.now().year and month == datetime.now().month)

        # 日付ボタン
        for r, week in enumerate(month_days):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(self.cal_frame, text="", width=4).grid(row=r+1, column=c)
                    continue

                # 祝祭日/日曜は赤、土曜は青、それ以外は黒
                try:
                    d_obj = date(self.year_var.get(), self.month_var.get(), day)
                    if jpholiday.is_holiday(d_obj) or c == 0:
                        fg = "red"
                    elif c == 6:
                        fg = "blue"
                    else:
                        fg = "black"
                except Exception:
                    fg = "black"

                bg = "yellow" if is_current_month and day == today else None

                btn = tk.Button(
                    self.cal_frame,
                    text=str(day),
                    width=4,
                    fg=fg,
                    bg=bg,
                    command=lambda d=day: self._select_date(d)
                )
                btn.grid(row=r+1, column=c)

    # -----------------------------
    # 日付選択時の処理
    # -----------------------------
    def _select_date(self, day):
        year = self.year_var.get()
        month = self.month_var.get()
        self.selected_date = f"{year:04d}-{month:02d}-{day:02d}"
        if self.window_key:
            try:
                save_window_position(self.master, self.window_key)
            except Exception:
                pass
        self.master.destroy()


# =============================
# 🕒 TimePicker クラス（時刻ピッカー）
# =============================
# クリックで時と分を選択して "HH:MM" を返す汎用モジュール
class TimePicker:
    """
    シンプルな時刻選択ダイアログ。
    00〜23時、00〜59分を選択して "HH:MM" を返す。


    例：
    tp = TimePicker(initial_time="07:30")
    result = tp.show()
    """
    def __init__(self, parent, initial_time="07:00", window_key: str | None = None):
        self.parent = parent
        try:
            h, m = map(int, initial_time.split(":"))
        except Exception:
            now = datetime.now()
            # 秒があれば切り上げて次の分
            base = now.replace(second=0, microsecond=0)
            if now.second or now.microsecond:
                base = base + timedelta(minutes=1)
            h, m = base.hour, base.minute

        self.hour = h
        self.minute = m
        self.selected_time = None
        self.window_key = window_key

    # -----------------------------
    def show(self):
        self.master = Toplevel(self.parent)
        self.master.title("時刻を選択")
        self.master.geometry("220x180")
        self.master.resizable(False, False)
        if self.window_key:
            try:
                load_window_position(self.master, self.window_key)
            except Exception:
                pass


        frame = tk.Frame(self.master)
        frame.pack(pady=20)


        # 時の選択
        tk.Label(frame, text="時：").grid(row=0, column=0)
        self.hour_var = tk.StringVar(value=f"{self.hour:02d}")
        hour_box = ttk.Combobox(frame,
        textvariable=self.hour_var,
        values=[f"{i:02d}" for i in range(24)],
        width=5,
        state="readonly"
        )
        hour_box.grid(row=0, column=1, padx=5)


        # 分の選択
        tk.Label(frame, text="分：").grid(row=1, column=0)
        self.minute_var = tk.StringVar(value=f"{self.minute:02d}")
        minute_box = ttk.Combobox(frame,
        textvariable=self.minute_var,
        values=[f"{i:02d}" for i in range(60)],
        width=5,
        state="readonly"
        )
        minute_box.grid(row=1, column=1, padx=5)


        # 決定ボタン
        ttk.Button(self.master, text="OK", width=12,
        command=self._commit
        ).pack(pady=15)


        self.master.wait_window()
        return self.selected_time

    # -----------------------------
    def _commit(self):
        h = self.hour_var.get()
        m = self.minute_var.get()
        self.selected_time = f"{h}:{m}"
        if self.window_key:
            try:
                save_window_position(self.master, self.window_key)
            except Exception:
                pass
        self.master.destroy()

