# -*- coding: utf-8 -*-
# pylint: disable=C0301,C0325
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
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional, cast

import tkinter as tk
from tkinter import ttk, messagebox, filedialog


from alarm.logger_bridge import get_alarm_logger


from alarm.constants import (
    REPEAT_DISPLAY,
    REPEAT_INTERNAL,
    COLUMN_LABELS_EDITOR,
    WEEKDAY_LABELS,
    DEFAULT_SOUND,
)

from alarm.json_editor_service import (
    ALARM_KEYS,
    ALARM_TEMPLATE,
    read_text_file,
    save_alarm_editor_json,
)
from alarm.mini_calendar import MiniCalendar, TimePicker
from utils.utils import normalize_alarm_input_dict

if TYPE_CHECKING:
    from alarm.logger_bridge import AlarmLogger


# -----------------------------------------------------
#  JSON Editor クラス
# -----------------------------------------------------
class JsonEditor:
    """alarms.json を修復・編集するための GUI ツール"""

    def __init__(
        self,
        master: tk.Misc,
        json_path: str | Path,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        self.json_path = Path(json_path)
        self.on_saved: Callable[[], None] | None = on_saved
        self.logger: AlarmLogger = get_alarm_logger()

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
            label: str = COLUMN_LABELS_EDITOR.get(col, col)
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
        y_scroll = ttk.Scrollbar(
            self.root, orient="vertical", command=self._on_tree_yview
        )
        x_scroll = ttk.Scrollbar(
            self.root, orient="horizontal", command=self._on_tree_xview
        )
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

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

    def _on_tree_yview(self, *args: object) -> None:
        """Scrollbar callback を Treeview.yview へ中継する。"""
        self.tree.yview(*args)  # type: ignore[no-untyped-call]

    def _on_tree_xview(self, *args: object) -> None:
        """Scrollbar callback を Treeview.xview へ中継する。"""
        self.tree.xview(*args)  # type: ignore[no-untyped-call]

    def _log_editor_warning(self, message: str, **context: object) -> None:
        """JSON editor の warning を context 付きで残す。"""
        self.logger.warning(message, context=context)

    def _log_editor_error(
        self,
        message: str,
        error: Exception | None = None,
        **context: object,
    ) -> None:
        """JSON editor の error を context 付きで残す。"""
        payload: Dict[str, object] = dict(context)
        if error is not None:
            payload["error"] = repr(error)
            payload["error_type"] = type(error).__name__
        self.logger.error(message, context=payload)

    # -------------------------------------------------
    #  JSON 読み込み＆修復
    # -------------------------------------------------
    def reload_from_file(self) -> None:
        """JSON ファイルを読み込み、可能な範囲で修復して rows に展開"""

        # ① 生データ読み込み
        try:
            raw: str = read_text_file(self.json_path)
        except FileNotFoundError:
            self._log_editor_error(
                "JSON file not found in JsonEditor.reload_from_file",
                json_path=str(self.json_path),
            )
            messagebox.showerror("エラー", f"JSONファイルが見つかりません:\n{self.json_path}")
            return
        except OSError as e:
            self._log_editor_error(
                "Failed to open JSON file in JsonEditor.reload_from_file",
                e,
                json_path=str(self.json_path),
            )
            messagebox.showerror("エラー", f"JSONファイルを開けませんでした:\n{e}")
            return

        # ② 軽症修復（safe_load_json）
        data: Any | None = self.safe_load_json(raw)

        # ③ 失敗したら heavy_repair_json へ
        if data is None:
            self._log_editor_warning(
                "safe_load_json returned None; trying heavy_repair_json",
                json_path=str(self.json_path),
                raw_length=len(raw),
            )
            messagebox.showwarning(
                "警告",
                "通常の修復に失敗しました。\n重症修復モード（heavy_repair）を試みます。"
            )

            data = self.heavy_repair_json(raw)

            if data is None:
                self._log_editor_error(
                    "heavy_repair_json failed to recover JSON",
                    json_path=str(self.json_path),
                    raw_length=len(raw),
                )
                messagebox.showerror(
                    "エラー",
                    "JSON修復に失敗しました（構造が壊れ過ぎています）"
                )
                return

        # ④ snooze_default / alarms抽出
        if isinstance(data, dict):
            typed_data: dict[str, Any] = cast(dict[str, Any], data)
            snooze_val = cast(int | str | None, typed_data.get("snooze_default", 10))
            self.snooze_default = (
                int(snooze_val) if snooze_val not in (None, "") else 10
            )
            alarms: list[Any] = cast(list[Any], typed_data.get("alarms", []))
        elif isinstance(data, list):
            self.snooze_default = 10
            alarms = cast(list[Any], data)
        else:
            self._log_editor_error(
                "Invalid JSON structure loaded in JsonEditor.reload_from_file",
                json_path=str(self.json_path),
                data=data,
                data_type=type(data).__name__,
            )
            messagebox.showerror("エラー", "JSON構造が不正です（dict または list が必要です）")
            return

        # ⑤ rows に整形して格納
        self.rows = []
        for a in alarms:
            if not isinstance(a, dict):
                continue
            alarm_dict: Dict[str, Any] = cast(Dict[str, Any], a)
            fixed: Dict[str, Any] = self.repair_alarm_dict(alarm_dict)
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
        text: str = raw_text

        # 1) "key": の後が空（値が無い）場合 → 空文字を補う
        text = re.sub(
            r'"([A-Za-z0-9_]+)"\s*:\s*(?=[,\}\]])',
            r'"\1": ""',
            text,
        )

        # 2) { の数と } の数を合わせる（必要なら } を補う）
        open_braces: int = text.count("{")
        close_braces: int = text.count("}")
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
        lines: List[str] = raw_text.splitlines()
        repaired_items: List[Dict[str, Any]] = []
        current: Dict[str, Any] = {}

        # キーバリューの正規表現
        pattern: re.Pattern[str] = re.compile(r'"(?P<key>[A-Za-z0-9_]+)"\s*:\s*(?P<value>.*)')

        for line in lines:
            line: str = line.strip()

            # 新しいオブジェクト開始の可能性
            if line.startswith("{") and current:
                repaired_items.append(current)
                current = {}

            m: re.Match[str] | None = pattern.search(line)
            if not m:
                continue

            key: str | Any = m.group("key")
            value: str | Any = m.group("value").rstrip(", ")

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
            fixed: Dict[str, Any] = self.repair_alarm_dict(item)
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
            s: str = v.strip().lower()
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
            s: str = v.strip()
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
            for x in cast(List[Any], v):
                try:
                    out.append(int(x))
                except (ValueError, TypeError):
                    continue
            return out
        if isinstance(v, str):
            s: str = v.strip()
            if not s:
                return []
            # JSON の文字列っぽいとき
            if s.startswith("[") and s.endswith("]"):
                try:
                    arr: Any = json.loads(s)
                    return self._to_list_int(arr)
                except (ValueError, TypeError, json.JSONDecodeError):
                    return []
            # カンマ区切り "1,3,5" など
            parts: List[str] = [p.strip() for p in s.split(",")]
            out: List[int] = []
            for p in parts:
                if not p:
                    continue
                try:
                    out.append(int(p))
                except (ValueError, TypeError):
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
        fixed: Dict[str, Any] = {}

        # 1) datetime / dt → date / time
        dt_raw: Any | None = d.get("datetime") or d.get("dt")
        date_str: str = d.get("date", "")
        time_str: str = d.get("time", "")

        if isinstance(dt_raw, str) and dt_raw:
            try:
                dt: datetime = datetime.fromisoformat(dt_raw)
                date_str = dt.strftime("%Y-%m-%d")
                time_str = dt.strftime("%H:%M")
            except ValueError:
                pass

        fixed["date"] = date_str
        fixed["time"] = time_str
        # pylint: disable=protected-access
        # 2) その他のキーをテンプレート順で埋める
        for key, template_val in ALARM_TEMPLATE.items():
            if key in ("date", "time"):
                continue

            val: Any = d.get(key, template_val)

            if val is None:
                val = template_val

            # --- 型補正 ---
            int_keys = (
                "id", "interval_weeks", "duration",
                "snooze_minutes", "snooze_limit",
                "_snooze_count"
            )
            if key in int_keys:
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    val = template_val

            elif key in ("enabled", "skip_holiday", "_triggered"):
                if isinstance(val, str):
                    val = val.lower() in (
                        "true", "1", "yes", "on"
                    )
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
        fixed = normalize_alarm_input_dict(fixed, ALARM_TEMPLATE)
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
        rep_raw: Any | None = alarm.get("repeat", "none")
        rep: Any | Literal['none'] = "none" if rep_raw is None else rep_raw
        d["repeat"] = REPEAT_DISPLAY.get(rep, rep)

        # weekday → 「月火水」
        wd_list: Any | None = alarm.get("weekday", [])
        if isinstance(wd_list, list):
            weekday_items: List[int] = [
                i for i in cast(List[Any], wd_list)
                if isinstance(i, int) and 0 <= i < len(WEEKDAY_LABELS)
            ]
            d["weekday"] = "".join(
                WEEKDAY_LABELS[i] for i in weekday_items
            )
        else:
            d["weekday"] = ""

        # week_of_month
        wom: Any | None = alarm.get("week_of_month", [])
        if isinstance(wom, list):
            wom_items: List[Any] = cast(List[Any], wom)
            d["week_of_month"] = ",".join(str(x) for x in wom_items)
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
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            self._log_editor_warning(
                "Skipped JsonEditor.refresh_tree because tree does not exist",
                rows=self.rows,
                rows_type=type(self.rows).__name__,
            )
            return

        self.tree.delete(*self.tree.get_children())

        for alarm in self.rows:
            disp: Dict[str, Any] = self.build_display_dict(alarm)
            row: List[Any] = [disp.get(key, "") for key in ALARM_KEYS]
            self.tree.insert("", "end", values=row)

    # -------------------------------------------------
    #  行追加 / 削除
    # -------------------------------------------------
    def add_row(self) -> None:
        """末尾に空の行を追加"""
        new_id: int = 1
        if self.rows:
            try:
                new_id: int = max(
                    int(r.get("id", 0)) for r in self.rows if str(r.get("id", "")).strip() != ""
                ) + 1
            except ValueError:
                self._log_editor_warning(
                    "Invalid id found while calculating new row id",
                    rows=self.rows,
                    rows_type=type(self.rows).__name__,
                )
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
        sel: tuple[str, ...] = self.tree.selection()
        if not sel:
            self._log_editor_warning(
                "Delete row requested without selection",
                selected_items=list(sel),
                rows=self.rows,
            )
            messagebox.showwarning("削除", "削除する行を選択してください。")
            return

        if not messagebox.askyesno("確認", f"{len(sel)} 件の行を削除しますか？"):
            return

        indices: List[int] = sorted(
            (self.tree.index(item_id) for item_id in sel), reverse=True
        )
        for idx in indices:
            if 0 <= idx < len(self.rows):
                del self.rows[idx]

        self.refresh_tree()

    # -------------------------------------------------
    #  セル編集（ダブルクリック）
    # -------------------------------------------------
    def on_double_click(self, event: tk.Event) -> str | None:
        """セルをダブルクリックしたときに適切なエディタを表示して編集する"""
        region: Literal["heading", "separator", "tree", "cell", "nothing"] = (
            self.tree.identify_region(event.x, event.y)
        )
        if region != "cell":
            return "break"

        item_id: str = self.tree.identify_row(event.y)
        col_id: str = self.tree.identify_column(event.x)  # "#1", "#2", ...
        if not item_id or col_id == "#0":
            return "break"

        # 行選択を強制（ダブルクリックで選択が外れるのを防ぐ）



        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self.tree.focus_set()

        row_index: int = self.tree.index(item_id)
        if not (0 <= row_index < len(self.rows)):
            return "break"

        col_index: int = int(col_id[1:]) - 1
        if not (0 <= col_index < len(ALARM_KEYS)):
            return "break"

        key: str = ALARM_KEYS[col_index]
        row: Dict[str, Any] = self.rows[row_index]

        bbox: tuple[int, int, int, int] | Literal[''] = self.tree.bbox(item_id, col_id)
        if not bbox:
            return "break"
        x, y, width, height = bbox

        def place_widget(widget: tk.Widget) -> None:
            widget.place(in_=self.tree, x=x, y=y, width=width, height=height)
            widget.focus_set()

            def on_focus_out(_event_: tk.Event[tk.Misc] | None = None) -> None:
                widget.destroy()
                # 編集後は表示更新
                self.refresh_tree()

            widget.bind("<FocusOut>", on_focus_out)

        # ---- key 別の編集ロジック ----

        # 日付（ミニカレンダー）
        if key == "date":
            current = str(row.get("date", ""))
            new_date: str | None = self.select_date_dialog(current or None)
            if new_date:
                row["date"] = new_date
                self.refresh_tree()
            return "break"

        # 時刻（TimePicker）
        if key == "time":
            current = str(row.get("time", ""))
            new_time: str | None = self.select_time_dialog(current or None)
            if new_time:
                row["time"] = new_time
                self.refresh_tree()
            return "break"

        # repeat（コンボボックス、日本語表示）
        if key == "repeat":
            internal: str = row.get("repeat", "none")
            current_label: str = REPEAT_DISPLAY.get(internal, "単発")

            cb = ttk.Combobox(self.tree, state="readonly")
            cb["values"] = list(REPEAT_INTERNAL.keys())
            cb.set(current_label)

            def commit_repeat(_event: tk.Event[tk.Misc] | None = None) -> None:
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
            weeks: List[int] | None
            wdays: List[int] | None
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
            current: Any = row.get("weekday", [])
            result: List[int] | None = self.select_weekdays_dialog(current)
            if result is not None:
                row["weekday"] = result
                self.refresh_tree()
            return "break"

        # ON/OFF 系
        if key in ("enabled", "skip_holiday", "_triggered"):
            cb = ttk.Combobox(self.tree, state="readonly")
            cb["values"] = ["✔", ""]
            cb.set("✔" if row.get(key) else "")

            def commit_boolean(_event: tk.Event[tk.Misc] | None = None) -> None:
                v = cb.get()
                row[key] = v == "✔"
                cb.destroy()
                self.refresh_tree()

            cb.bind("<<ComboboxSelected>>", commit_boolean)
            cb.bind("<Return>", commit_boolean)
            place_widget(cb)
            return "break"

        # 数値系
        if key in ("interval_weeks", "duration", "snooze_minutes", "snooze_limit", "_snooze_count"):
            entry = ttk.Entry(self.tree)
            entry.insert(0, str(row.get(key, "")))

            def commit_numeric(_event: tk.Event[tk.Misc] | None = None) -> None:
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

        def commit_generic(_event: tk.Event[tk.Misc] | None = None) -> None:
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
        parsed_initial_date: date | None = None
        if initial_date:
            try:
                parsed_initial_date = datetime.strptime(initial_date, "%Y-%m-%d").date()
            except ValueError:
                parsed_initial_date = None

        cal = MiniCalendar(self.root, initial_date=parsed_initial_date)
        selected_date = cal.show()
        if selected_date is None:
            return None
        return selected_date.strftime("%Y-%m-%d")

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
            var = tk.BooleanVar(value=i in (initial_weeks or []))
            ttk.Checkbutton(week_frame, text=f"第{i}週", variable=var).pack(
                side="left", padx=4
            )
            week_vars.append(var)

        ttk.Label(win, text="曜日を選択").pack(pady=(6, 2))
        wd_frame = ttk.Frame(win)
        wd_frame.pack(pady=(0, 6))
        wd_vars: list[tk.BooleanVar] = []
        for i, label in enumerate(WEEKDAY_LABELS):
            var = tk.BooleanVar(value=i in (initial_weekday or []))
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

        try:
            save_alarm_editor_json(
                path=self.json_path,
                snooze_default=self.snooze_default,
                alarms=alarms,
            )
            messagebox.showinfo("保存", "JSONファイルを正常に保存しました。")
            if self.on_saved is not None:
                self.on_saved()
        except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
            self._log_editor_error(
                "Failed to save JSON from JsonEditor.save_json",
                e,
                json_path=str(self.json_path),
                snooze_default=self.snooze_default,
                alarms=alarms,
            )
            messagebox.showerror("保存エラー", str(e))
