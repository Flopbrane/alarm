# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
#
#########################
# -*- coding: utf-8 -*-
"""
build_unused_definitions_json.py

definition_map.csv と
build_reference_report.py 実行時に保存された used_definitions.json を元に、

- unused_definitions.json（未使用定義）
を生成する。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

# ===============================
# 設定
# ===============================

PROJECT_ROOT: Path = Path(r"D:\PC\Python\alarm").resolve()

SCRIPT_DIR: Path = Path(__file__).resolve().parent
DEF_DIR: Path = SCRIPT_DIR / "definition_map"
REF_DIR: Path = SCRIPT_DIR / "reference_report"
OUT_DIR: Path = SCRIPT_DIR / "unused_report"

DEF_CSV: Path = DEF_DIR / "definition_map.csv"

# build_reference_report.py 側で保存する想定
USED_JSON: Path = REF_DIR / "used_definitions.json"

OUT_UNUSED_JSON: Path = OUT_DIR / "unused_definitions.json"
OUT_ALL_JSON: Path = OUT_DIR / "all_definitions.json"

# ===============================
# 定義CSV → 全定義JSON
# ===============================


def load_all_definitions() -> dict[str, dict[str, str | int]]:
    """
    戻り値:
    {
      "file_key:qualname": {
          "file_key": "...",
          "qualname": "...",
          "lineno": int
      }
    }
    """
    defs: dict[str, dict[str, str | int]] = {}
    current_class: dict[str, str | None] = {}

    with DEF_CSV.open(encoding="utf-8-sig") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        reader.fieldnames = [
            (h or "").replace('"', "").replace("\ufeff", "").strip()
            for h in (reader.fieldnames or [])
        ]

        for row in reader:
            file_key: str | Any = row["file_key"]
            kind: str | Any = row["kind"]
            name: str | Any = row["name"]
            lineno: int = int(row["lineno"])
            indent: int = int(row["indent"])

            if file_key not in current_class:
                current_class[file_key] = None

            if kind == "class" and indent == 0:
                qual = str(name)
                defs[f"{file_key}:{qual}"] = {
                    "file_key": file_key,
                    "qualname": qual,
                    "lineno": lineno,
                }
                current_class[file_key] = name

            elif kind == "def":
                if indent == 0:
                    qual = f"__functions__.{name}"
                    defs[f"{file_key}:{qual}"] = {
                        "file_key": file_key,
                        "qualname": qual,
                        "lineno": lineno,
                    }
                    current_class[file_key] = None

                elif indent == 4:
                    cls: str | None = current_class.get(file_key)
                    if cls:
                        qual: str= f"{cls}.{name}"
                        defs[f"{file_key}:{qual}"] = {
                            "file_key": file_key,
                            "qualname": qual,
                            "lineno": lineno,
                        }

    return defs


# ===============================
# main
# ===============================


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_defs: dict[str, dict[str, str | int]] = load_all_definitions()

    # 使用中定義（参照解析結果）
    if USED_JSON.exists():
        used_defs: set[str] = set(json.loads(USED_JSON.read_text(encoding="utf-8")))
    else:
        print("[WARN] used_definitions.json not found. 全定義を未使用扱いにします。")
        used_defs = set()

    unused_defs: dict[str, dict[str, str | int]] = {k: v for k, v in all_defs.items() if k not in used_defs}

    # 出力
    OUT_ALL_JSON.write_text(
        json.dumps(all_defs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    OUT_UNUSED_JSON.write_text(
        json.dumps(unused_defs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("JSON generated:")
    print(f"- all:    {OUT_ALL_JSON}")
    print(f"- unused: {OUT_UNUSED_JSON}")
    print(f"Unused count: {len(unused_defs)}")


if __name__ == "__main__":
    main()
# ===============================
