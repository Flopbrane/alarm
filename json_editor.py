# -*- coding: utf-8 -*-
#########################
# Author: F.Kurokawa
# Description:
# JSON エディターツール（alarms.json 修復 & 編集）
#########################

"""
json_editor.py

・壊れた JSON（値抜け、カッコ不足など）をできるだけ読み込んで復旧
・ALARM_KEYS に基づいた表形式で一覧表示
・GUI と同じイメージで、日付/時刻/繰り返し/曜日/ON/OFF などを編集
・保存時には「完全に JSON として正しい形式」に正規化して書き出す

AlarmManager とは「ファイルパス」だけを共有し、
内部の alarms リストは直接触らないようにしている（循環参照防止）。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from alarm_manager import AlarmManager
from mini_calendar import MiniCalendar, TimePicker
from constants import (
    REPEAT_DISPLAY,
    REPEAT_INTERNAL,
    ALARM_KEYS,
    COLUMN_LABELS_EDITOR,
    WEEKDAY_LABELS,
    DEFAULT_SOUND,
    ALARM_TEMPLATE
)
from utils import (
    normalize_alarm_dict
)




# -----------------------------------------------------
#  JSON Editor クラス
# -----------------------------------------------------
class JsonEditor:
    """alarms.json を修復・編集するための GUI ツール"""

    def __init__(self, master: tk.Misc, manager: AlarmManager) -> None:
        self.manager = manager
        # ✅ 編集対象 JSON ファイル
        self.json_path = manager.save_file_path

        # 編集用メモリ上データ（各行 = 1アラームの dict）
        self.rows: List[Dict[str, Any]] = []
        self.snooze_default: int = 10  # ファイルにあれば上書き

        # ----- ウインドウ構築 -----
        self.root = tk.Toplevel(master)
        self.root.title("JSON 修復エディター（alarms.json）")
        self.root.geometry("1200x500")
        self.root.resizable(True, True)

        # Treeview（横長テーブル）
        self.tree = ttk.Treeview(
            self.root,
            columns=ALARM_KEYS,
            show="headings",
            height=18,
        )

        # 列ヘッダ / 幅
        for col in ALARM_KEYS:
            label = COLUMN_LABELS_EDITOR.get(col, col)
            self.tree.heading(col, text=label)
            width = 140
            if col in ("id", "interval_weeks", "snooze_limit"):
                width = 70
            elif col in ("weekday", "week_of_month"):
                width = 110
            elif col in ("_triggered", "enabled", "skip_holiday"):
                width = 90
            self.tree.column(col, width=width, anchor="center")

        # スクロールバー
        y_scroll = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(self.root, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=y_scroll.set, xscroll=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        # ウインドウのグリッド拡張
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        # ボタン群
        btn_frame = ttk.Frame(self.root)
        btn_frame.grid(row=2, column=0, pady=8)

        ttk.Button(btn_frame, text="行を追加", command=self.add_row).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="選択行を削除", command=self.delete_row).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="再読み込み", command=self.reload_from_file).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="保存", command=self.save_json).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="閉じる", command=self.root.destroy).pack(side="left", padx=6)

        # ダブルクリックで編集
        self.tree.bind("<Double-1>", self.on_double_click)

        # 初回読み込み
        self.reload_from_file()

    # -------------------------------------------------
    #  JSON 読み込み＆修復
    # -------------------------------------------------
    def reload_from_file(self) -> None:
        """JSON ファイルを読み込み、可能な範囲で修復して rows に展開"""

        # ① 生データ読み込み
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                raw = f.read()
        except FileNotFoundError:
            messagebox.showerror("エラー", f"JSONファイルが見つかりません:\n{self.json_path}")
            return
        except FileExistsError as e:
            messagebox.showerror("エラー", f"JSONファイルを開けませんでした:\n{e}")
            return

        # ② 軽症修復（safe_load_json）
        data = self.safe_load_json(raw)

        # ③ 失敗したら heavy_repair_json へ
        if data is None:
            messagebox.showwarning(
                "警告",
                "通常の修復に失敗しました。\n重症修復モード（heavy_repair）を試みます。"
            )

            data = self.heavy_repair_json(raw)

            if data is None:
                messagebox.showerror(
                    "エラー",
                    "JSON修復に失敗しました（構造が壊れ過ぎています）"
                )
                return

        # ④ snooze_default / alarms抽出
        if isinstance(data, dict):
            self.snooze_default = int(data.get("snooze_default", 10) or 10)
            alarms = data.get("alarms", [])
        elif isinstance(data, list):
            self.snooze_default = 10
            alarms = data
        else:
            messagebox.showerror("エラー", "JSON構造が不正です（dict または list が必要です）")
            return

        # ⑤ rows に整形して格納
        self.rows = []
        for a in alarms:
            if not isinstance(a, dict):
                continue
            fixed = self.repair_alarm_dict(a)
            self.rows.append(fixed)

        # ⑥ 表示更新
        self.refresh_tree()

    # -------------------------------------------------
    # JSON 修復ヘルパー(軽症〜中症)
    # -------------------------------------------------
    def safe_load_json(self, raw_text: str) -> Optional[Any]:
        """
        壊れた JSON を可能な限り読み込んで Python オブジェクトに変換する。

        ・値抜け（"key": ,）→ "key": "" に補完
        ・カッコ不足 → '}' を追加して調整
        """
        text = raw_text

        # 1) "key": の後が空（値が無い）場合 → 空文字を補う
        text = re.sub(
            r'"([A-Za-z0-9_]+)"\s*:\s*(?=[,\}\]])',
            r'"\1": ""',
            text,
        )

        # 2) { の数と } の数を合わせる（必要なら } を補う）
        open_braces = text.count("{")
        close_braces = text.count("}")
        if open_braces > close_braces:
            text += "}" * (open_braces - close_braces)

        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None

    # -------------------------------------------------
    # JSON 修復ヘルパー(重症)
    # -------------------------------------------------
    def heavy_repair_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        JSON が重症レベルで壊れている場合の最終修復関数。
        行単位でキーを抽出して疑似 JSON を復元する。
        """
        lines = raw_text.splitlines()
        repaired_items: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}

        # キーバリューの正規表現
        pattern = re.compile(r'"(?P<key>[A-Za-z0-9_]+)"\s*:\s*(?P<value>.*)')

        for line in lines:
            line = line.strip()

            # 新しいオブジェクト開始の可能性
            if line.startswith("{") and current:
                repaired_items.append(current)
                current = {}

            m = pattern.search(line)
            if not m:
                continue

            key = m.group("key")
            value = m.group("value").rstrip(", ")

            # 値が空 → "" を補完
            if value == "" or value is None:
                current[key] = ""
                continue

            # JSON 文字列を安全に値として読み込む
            try:
                if value.startswith('"') and value.endswith('"'):
                    current[key] = value.strip('"')
                elif value.startswith("[") and value.endswith("]"):
                    current[key] = json.loads(value)
                else:
                    # true / false / null / 数値などの可能性
                    try:
                        current[key] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        current[key] = value
            except ValueError:
                current[key] = ""

        if current:
            repaired_items.append(current)

        # ALARM_KEYS に補正して完全な辞書に整形
        fixed_items: List[Dict[str, Any]] = []
        for item in repaired_items:
            fixed = self.repair_alarm_dict(item)
            fixed_items.append(fixed)

        return {"alarms": fixed_items}

    # -------------------------------------------------
    #  各種変換ヘルパー
    # -------------------------------------------------
    def _to_bool(self, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1", "on", "yes", "y", "✔"):
                return True
            if s in ("false", "0", "off", "no", "n", "", "null"):
                return False
        return False

    def _to_int(self, v: Any, default: int = 0) -> int:
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
        if isinstance(v, str):
            s = v.strip()
            if s == "":
                return default
            try:
                return int(s)
            except ValueError:
                return default
        return default

    def _to_list_int(self, v: Any) -> List[int]:
        if isinstance(v, list):
            out: List[int] = []
            for x in v:
                try:
                    out.append(int(x))
                except TypeError:
                    continue
            return out
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            # JSON の文字列っぽいとき
            if s.startswith("[") and s.endswith("]"):
                try:
                    arr = json.loads(s)
                    return self._to_list_int(arr)
                except ValueError:
                    return []
            # カンマ区切り "1,3,5" など
            parts = [p.strip() for p in s.split(",")]
            out: List[int] = []
            for p in parts:
                if not p:
                    continue
                try:
                    out.append(int(p))
                except TypeError:
                    continue
            return out
        return []

    # -------------------------------------------------
    #  行データの補正（internal-handler 方式）
    # -------------------------------------------------
    def repair_alarm_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """
        壊れた alarm dict を ALARM_TEMPLATE を基準に
        完全に正規化した dict にして返す。
        ・未知キーは無視
        ・テンプレートの不足キーは全部埋める
        ・型変換変換（bool, int, list, datetime）はこの中で完結
        """
        fixed = {}

        # 1) datetime / dt → date / time
        dt_raw = d.get("datetime") or d.get("dt")
        date_str = d.get("date", "")
        time_str = d.get("time", "")


        if isinstance(dt_raw, str) and dt_raw:
            try:
                dt = datetime.fromisoformat(dt_raw)
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M")
            except ValueError:
                pass


        fixed["date"] = date_str
        fixed["time"] = time_str
        # pylint: disable=protected-access
        # 2) その他のキーをテンプレート順で埋める
        for key in ALARM_TEMPLATE:
            if key in ("date", "time"):
                continue

            val = d.get(key, ALARM_TEMPLATE[key])

            if val is None:
                val = ALARM_TEMPLATE[key]

            # --- 型補正 ---
            if key in ("id", "interval_weeks", "duration", "snooze_minutes", "snooze_limit", "_snooze_count"):
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    val = ALARM_TEMPLATE[key]


            elif key in ("enabled", "skip_holiday", "_triggered"):
                if isinstance(val, str):
                    val = val.lower() in ("true", "1", "yes", "on")
                else:
                    val = bool(val)


            elif key in ("weekday", "week_of_month"):
                if not isinstance(val, list):
                    val = []


            elif key == "_snoozed_until":
                if val in ("", None, "null"):
                    val = None
            # その他のキーはそのまま保持

            fixed[key] = val

            fixed = normalize_alarm_dict(fixed, ALARM_TEMPLATE)
        # pylint: enable=protected-access

        return fixed

    # -------------------------------------------------
    #  表示用 dict 作成（内部値 → GUI 用文字列）
    # -------------------------------------------------
    def build_display_dict(self, alarm: Dict[str, Any]) -> Dict[str, Any]:
        """表示用 dict 作成（内部値 → GUI 用文字列） """
        d: Dict[str, Any] = {}

        def _val(key: str) -> str:
            v = alarm.get(key, "")
            return "" if v is None else str(v)

        d["id"] = _val("id")
        d["name"] = _val("name")
        d["date"] = _val("date")
        d["time"] = _val("time")

        # repeat → 日本語
        rep_raw = alarm.get("repeat", "none")
        rep = "none" if rep_raw is None else rep_raw
        d["repeat"] = REPEAT_DISPLAY.get(rep, rep)

        # weekday → 「月火水」
        wd_list = alarm.get("weekday", [])
        if isinstance(wd_list, list):
            d["weekday"] = "".join(
                WEEKDAY_LABELS[i] for i in wd_list if isinstance(i, int) and 0 <= i < len(WEEKDAY_LABELS)
            )
        else:
            d["weekday"] = ""

        # week_of_month
        wom = alarm.get("week_of_month", [])
        if isinstance(wom, list):
            d["week_of_month"] = ",".join(str(x) for x in wom)
        else:
            d["week_of_month"] = ""

        d["interval_weeks"] = _val("interval_weeks")
        d["base_date"] = _val("base_date")
        d["custom_desc"] = _val("custom_desc")

        # boolean → ✔ / 空
        d["enabled"] = "✔" if alarm.get("enabled") else ""
        d["skip_holiday"] = "✔" if alarm.get("skip_holiday") else ""

        d["sound"] = _val("sound")
        d["duration"] = _val("duration")
        d["snooze_minutes"] = _val("snooze_minutes")
        d["snooze_limit"] = _val("snooze_limit")
        d["_snooze_count"] = _val("_snooze_count")
        d["_snoozed_until"] = _val("_snoozed_until")
        d["_triggered"] = "✔" if alarm.get("_triggered") else ""

        print("dict display:", d)

        return d

    # -------------------------------------------------
    #  Treeview 表示
    # -------------------------------------------------
    def refresh_tree(self) -> None:
        """self.rows から Treeview を再構築する"""
        self.tree.delete(*self.tree.get_children())

        for alarm in self.rows:
            disp = self.build_display_dict(alarm)
            row = [disp.get(key, "") for key in ALARM_KEYS]
            self.tree.insert("", "end", values=row)

    # -------------------------------------------------
    #  行追加 / 削除
    # -------------------------------------------------
    def add_row(self) -> None:
        """末尾に空の行を追加"""
        new_id = 1
        if self.rows:
            try:
                new_id = max(
                    int(r.get("id", 0)) for r in self.rows if str(r.get("id", "")).strip() != ""
                ) + 1
            except ValueError:
                new_id = len(self.rows) + 1

        row: Dict[str, Any] = {
            "id": new_id,
            "name": "",
            "date": "",
            "time": "",
            "repeat": "none",
            "weekday": [],
            "week_of_month": [],
            "interval_weeks": 1,
            "base_date": "",
            "custom_desc": "",
            "enabled": True,
            "sound": DEFAULT_SOUND,
            "skip_holiday": False,
            "duration": 10,
            "snooze_minutes": 10,
            "snooze_limit": 3,
            "_snooze_count": 0,
            "_snoozed_until": "",
            "_triggered": False,
        }
        self.rows.append(row)
        self.refresh_tree()

    def delete_row(self) -> None:
        """選択された行を削除"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("削除", "削除する行を選択してください。")
            return

        if not messagebox.askyesno("確認", f"{len(sel)} 件の行を削除しますか？"):
            return

        indices = sorted((self.tree.index(item_id) for item_id in sel), reverse=True)
        for idx in indices:
            if 0 <= idx < len(self.rows):
                del self.rows[idx]

        self.refresh_tree()

    # -------------------------------------------------
    #  セル編集（ダブルクリック）
    # -------------------------------------------------
    def on_double_click(self, event) -> None:
        """セルをダブルクリックしたときに適切なエディタを表示して編集する"""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return "break"

        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)  # "#1", "#2", ...
        if not item_id or col_id == "#0":
            return "break"

        # 行選択を強制（ダブルクリックで選択が外れるのを防ぐ）
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.focus_set()

        row_index = self.tree.index(item_id)
        if not (0 <= row_index < len(self.rows)):
            return "break"

        col_index = int(col_id[1:]) - 1
        if not (0 <= col_index < len(ALARM_KEYS)):
            return "break"

        key = ALARM_KEYS[col_index]
        row = self.rows[row_index]

        bbox = self.tree.bbox(item_id, col_id)
        if not bbox:
            return "break"
        x, y, width, height = bbox

        def place_widget(widget: tk.Widget) -> None:
            widget.place(in_=self.tree, x=x, y=y, width=width, height=height)
            widget.focus_set()

            def on_focus_out(event=None):
                widget.destroy()
                # 編集後は表示更新
                self.refresh_tree()

            widget.bind("<FocusOut>", on_focus_out)

        # ---- key 別の編集ロジック ----

        # 日付（ミニカレンダー）
        if key == "date":
            current = str(row.get("date", ""))
            new_date = self.select_date_dialog(current or None)
            if new_date:
                row["date"] = new_date
                self.refresh_tree()
            return "break"

        # 時刻（TimePicker）
        if key == "time":
            current = str(row.get("time", ""))
            new_time = self.select_time_dialog(current or None)
            if new_time:
                row["time"] = new_time
                self.refresh_tree()
            return "break"

        # repeat（コンボボックス、日本語表示）
        if key == "repeat":
            internal = row.get("repeat", "none")
            current_label = REPEAT_DISPLAY.get(internal, "単発")

            cb = ttk.Combobox(self.tree, state="readonly")
            cb["values"] = list(REPEAT_INTERNAL.keys())
            cb.set(current_label)

            def commit_repeat(event=None):
                label = cb.get()
                internal_val = REPEAT_INTERNAL.get(label, "none")
                row["repeat"] = internal_val

                # weekly_x 系の interval_weeks も揃える
                if internal_val.startswith("weekly_"):
                    try:
                        row["interval_weeks"] = int(internal_val.split("_")[1])
                    except ValueError:
                        row["interval_weeks"] = 1

                cb.destroy()
                self.refresh_tree()

            cb.bind("<<ComboboxSelected>>", commit_repeat)
            cb.bind("<Return>", commit_repeat)
            place_widget(cb)
            return "break"

        # 第n週（カスタム選択ダイアログで曜日も同時編集）
        if key == "week_of_month":
            weeks, wdays = self.select_custom_repeat_dialog(
                initial_weeks=row.get("week_of_month", []),
                initial_weekday=row.get("weekday", []),
            )
            if weeks is not None:
                row["week_of_month"] = weeks
                row["weekday"] = wdays
                self.refresh_tree()
            return "break"

        # 曜日（チェックボックスダイアログ）
        if key == "weekday":
            current = row.get("weekday", [])
            result = self.select_weekdays_dialog(current)
            if result is not None:
                row["weekday"] = result
                self.refresh_tree()
            return "break"

        # ON/OFF 系
        if key in ("enabled", "skip_holiday", "_triggered"):
            cb = ttk.Combobox(self.tree, state="readonly")
            cb["values"] = ["✔", ""]
            cb.set("✔" if row.get(key) else "")

            def commit_boolean(event=None):
                v = cb.get()
                row[key] = (v == "✔")
                cb.destroy()
                self.refresh_tree()

            cb.bind("<<ComboboxSelected>>", commit_boolean)
            cb.bind("<Return>", commit_boolean)
            place_widget(cb)
            return

        # 数値系
        if key in ("interval_weeks", "duration", "snooze_minutes", "snooze_limit", "_snooze_count"):
            entry = ttk.Entry(self.tree)
            entry.insert(0, str(row.get(key, "")))

            def commit_numeric(event=None):
                text = entry.get().strip()
                if text == "":
                    entry.destroy()
                    self.refresh_tree()
                    return
                try:
                    row[key] = int(text)
                except(ValueError, TypeError):
                    messagebox.showwarning("入力エラー", "整数値を入力してください。")
                entry.destroy()
                self.refresh_tree()

            entry.bind("<Return>", commit_numeric)
            place_widget(entry)
            return

        # サウンドファイル
        if key == "sound":
            initial = row.get("sound") or DEFAULT_SOUND
            path = filedialog.askopenfilename(
                title="音ファイルを選択",
                initialfile=initial,
                filetypes=[("WAV ファイル", "*.wav"), ("すべてのファイル", "*.*")],
            )
            if path:
                row["sound"] = path
                self.refresh_tree()
            return

        # それ以外 → テキスト編集
        entry = ttk.Entry(self.tree)
        entry.insert(0, str(row.get(key, "")))

        def commit_generic(event=None):
            row[key] = entry.get()
            entry.destroy()
            self.refresh_tree()

        entry.bind("<Return>", commit_generic)
        place_widget(entry)

    # -------------------------------------------------
    #  各種ダイアログ
    # -------------------------------------------------
    def select_date_dialog(self, initial_date: Optional[str] = None) -> Optional[str]:
        """ミニカレンダーを開き、YYYY-MM-DD を返す"""
        cal = MiniCalendar(self.root, initial_date)
        return cal.show()

    def select_time_dialog(self, initial_time: Optional[str] = None) -> Optional[str]:
        """TimePicker を開き、HH:MM を返す"""
        tp = TimePicker(self.root, initial_time or "07:00")
        return tp.show()

    def select_weekdays_dialog(self, initial: Optional[List[int]] = None) -> Optional[List[int]]:
        """曜日選択ダイアログを開き、[0..6] のリストを返す"""
        selected = set(initial or [])

        win = tk.Toplevel(self.root)
        win.title("曜日の選択")
        win.resizable(False, False)

        ttk.Label(win, text="曜日を選択してください", font=("Meiryo", 11, "bold")).pack(pady=6)

        frame = ttk.Frame(win)
        frame.pack(padx=10, pady=4)

        vars_: List[tk.IntVar] = []

        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.IntVar(value=1 if i in selected else 0)
            chk = ttk.Checkbutton(frame, text=label, variable=var)
            chk.grid(row=0, column=i, padx=4, pady=2)
            vars_.append(var)

        result: List[int] = []

        def ok():
            result.clear()
            for i, var in enumerate(vars_):
                if var.get():
                    result.append(i)
            win.destroy()

        def cancel():
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=8)

        ttk.Button(btn_frame, text="OK", width=8, command=ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="キャンセル", width=8, command=cancel).pack(side="left", padx=5)

        win.grab_set()
        win.wait_window()

        return result

    def select_custom_repeat_dialog(
        self,
        initial_weeks: Optional[List[int]] = None,
        initial_weekday: Optional[List[int]] = None,
    ) -> tuple[Optional[List[int]], Optional[List[int]]]:
        """第n週と曜日をまとめて設定する簡易ダイアログ"""
        win = tk.Toplevel(self.root)
        win.title("カスタム繰り返し設定")
        win.resizable(False, False)

        ttk.Label(win, text="第n週を選択").pack(pady=(8, 2))
        week_frame = ttk.Frame(win)
        week_frame.pack(pady=(0, 6))
        week_vars: list[tk.BooleanVar] = []
        for i in range(1, 6):
            var = tk.BooleanVar(value=(i in (initial_weeks or [])))
            ttk.Checkbutton(week_frame, text=f"第{i}週", variable=var).pack(side="left", padx=4)
            week_vars.append(var)

        ttk.Label(win, text="曜日を選択").pack(pady=(6, 2))
        wd_frame = ttk.Frame(win)
        wd_frame.pack(pady=(0, 6))
        wd_vars: list[tk.BooleanVar] = []
        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.BooleanVar(value=(i in (initial_weekday or [])))
            ttk.Checkbutton(wd_frame, text=label, variable=var).pack(side="left", padx=4)
            wd_vars.append(var)

        result_weeks: List[int] = []
        result_wdays: List[int] = []

        def on_ok():
            result_weeks.clear()
            result_wdays.clear()
            for i, v in enumerate(week_vars, start=1):
                if v.get():
                    result_weeks.append(i)
            for i, v in enumerate(wd_vars):
                if v.get():
                    result_wdays.append(i)
            win.destroy()

        def on_cancel():
            result_weeks.clear()
            result_wdays.clear()
            win.destroy()

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="OK", width=8, command=on_ok).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="キャンセル", width=8, command=on_cancel).pack(side="left", padx=5)

        win.grab_set()
        win.wait_window()

        if not result_weeks and not result_wdays:
            return None, None
        return result_weeks, result_wdays

    # -------------------------------------------------
    #  保存
    # -------------------------------------------------
    def save_json(self) -> None:
        """現在の rows を JSON として self.json_path に保存"""

        alarms: List[Dict[str, Any]] = []
        for row in self.rows:
            fixed = self.repair_alarm_dict(row)
            alarms.append(fixed)

        save_data = {
            "snooze_default": self.snooze_default,
            "alarms": alarms,
        }

        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, ensure_ascii=False, indent=4)
            messagebox.showinfo("保存", "JSONファイルを正常に保存しました。")
            # 🔄 AlarmManager 側も再読み込みしておくと安全
            # pylint: disable=protected-access
            try:
                self.manager.load_all()
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            # pylint: enable=protected-access
        except(FileNotFoundError, json.JSONDecodeError) as e:
            messagebox.showerror("保存エラー", str(e))
