# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
#########################
# Author: F.Kurokawa
# Description:
# 基準CSVファイルから定義マップJSONを生成
#########################
"""
build_definition_map_json.py

PowerShell で生成した definition_map.csv から、
ファイル単位の「定義マップ（JSON）」を作成する。

JSON 構造（例）:
{
  "alarm_config_manager.py": {
    "__functions__": ["set_default_mode", "set_last_mode"],
    "Config": [],
    "ConfigManager": ["_normalize_mode", "get_config_path", "load_config"]
  },
  "utils/datetime_utils.py": {
    "__functions__": ["parse_date", "format_date"]
  }
}

設計ルール:
- file_key（alarm 相対パス）をトップキーにする
- indent == 0 の def → "__functions__"
- indent == 0 の class → クラス定義
- indent == 4 の def → 直前のクラスのメソッド
- indent >= 8 の def → 内部関数（今回は無視）
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import defaultdict
from typing import Any

# ===============================
# ★ 設定項目
# ===============================

# 通常運用（contents_class_def 配下想定）
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# 他プロジェクトで使う場合（必要ならコメント解除）
# PROJECT_ROOT = Path(r"D:\PC\Python\another_project").resolve()

SCRIPT_DIR: Path = Path(__file__).resolve().parent

CSV_PATH: Path = SCRIPT_DIR / "definition_map" / "definition_map.csv"
OUT_DIR: Path = SCRIPT_DIR / "definition_map"
OUT_JSON: Path = OUT_DIR / "definition_map.json"

# 安全チェック（任意）
if PROJECT_ROOT.name.lower() != "alarm":
    print(f"[INFO] PROJECT_ROOT = {PROJECT_ROOT}")

# ===============================
# メイン処理
# ===============================
def build_definition_map(csv_path: Path) -> dict[str, dict[str, list[str]]]:
    """
    CSV を読み込み、定義マップ dict を生成する
    """
    # file_key -> {"__functions__": set(), "ClassName": set(), ...}
    defs: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    # file_key ごとの「現在のクラス」を追跡
    current_class: dict[str, str | None] = {}

    with csv_path.open(encoding="utf-8-sig") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)

        # ヘッダ名を正規化（BOM・クォート除去）
        if reader.fieldnames:
            reader.fieldnames = [
                h.replace('"', "").replace("\ufeff", "").strip() for h in reader.fieldnames
            ]

        for row in reader:
            file_key: str | Any = row["file_key"]
            kind: str | Any = row["kind"]
            name: str | Any = row["name"]
            indent = int(row["indent"])

            # 初期化
            if "__functions__" not in defs[file_key]:
                defs[file_key]["__functions__"] = set()
            if file_key not in current_class:
                current_class[file_key] = None

            if kind == "class" and indent == 0:
                # クラス定義
                # 明示的に空 set を作成（既存があれば上書きしない）
                defs[file_key].setdefault(name, set())
                current_class[file_key] = name

            elif kind == "def":
                if indent == 0:
                    # ファイル直下の関数
                    defs[file_key]["__functions__"].add(name)
                    current_class[file_key] = None

                elif indent == 4:
                    # クラス直下のメソッド（直前クラスに紐づけ）
                    cls: str | None = current_class.get(file_key)
                    if cls:
                        defs[file_key][cls].add(name)

                else:
                    # indent >= 8 は内部関数として無視
                    pass

    # set → sorted list に変換
    out: dict[str, dict[str, list[str]]] = {}
    for file_key, items in defs.items():
        out[file_key] = {}
        for k, v in items.items():
            out[file_key][k] = sorted(v)

    return out


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    definition_map: dict[str, dict[str, list[str]]] = build_definition_map(CSV_PATH)

    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(definition_map, f, ensure_ascii=False, indent=2)

    print("JSON definition map generated:")
    print(OUT_JSON)
    print(f"Files: {len(definition_map)}")

    # デバッグ表示（最初の数ファイル）
    print("\n--- SAMPLE ---")
    for i, (k, v) in enumerate(definition_map.items()):
        print(k, "=>", v)
        if i >= 2:
            break


if __name__ == "__main__":
    main()
# EOF
