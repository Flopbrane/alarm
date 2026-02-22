from __future__ import annotations

# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
#
#########################
# -*- coding: utf-8 -*-
"""
build_unused_definitions_report.py

definition_map.csv と reference_report 用の解析結果を使って、
「どこからも参照されていない定義（関数・メソッド）」を一覧表示する。
"""


import csv
import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List

# ===============================
# 設定
# ===============================

PROJECT_ROOT: Path = Path(r"D:\PC\Python\alarm").resolve()

SCRIPT_DIR: Path = Path(__file__).resolve().parent
DEF_DIR: Path = SCRIPT_DIR / "definition_map"

DEF_CSV: Path = DEF_DIR / "definition_map.csv"
DEF_JSON: Path = DEF_DIR / "definition_map.json"
REF_REPORT_DIR: Path = SCRIPT_DIR / "reference_report"
REF_HTML: Path = REF_REPORT_DIR / "reference_report.html"

OUT_DIR: Path = SCRIPT_DIR / "unused_report"
OUT_HTML: Path = OUT_DIR / "unused_definitions.html"
# ===============================
# ユーティリティ
# ===============================


def vscode_link(file_key: str, lineno: int) -> str:
    """VSCode で開くリンクを生成"""
    abs_path: Path = (PROJECT_ROOT / file_key).resolve()
    uri: str = str(abs_path).replace("\\", "/")
    return f"vscode://file/{uri}:{lineno}"


# ===============================
# 定義一覧を読む
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

    with DEF_CSV.open(encoding="utf-8-sig") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        reader.fieldnames = [
            h.replace('"', "").replace("\ufeff", "").strip()
            for h in reader.fieldnames or []
        ]

        current_class: dict[str, str | None] = {}

        for row in reader:
            # Cast CSV values to str to avoid typing ambiguities from csv.Any
            file_key: str = str(row["file_key"])
            kind: str = str(row["kind"])
            name: str = str(row["name"])
            lineno = int(row["lineno"])
            indent = int(row["indent"])

            if file_key not in current_class:
                current_class[file_key] = None

            if kind == "class" and indent == 0:
                qual = name
                key: str = f"{file_key}:{qual}"
                defs[key] = {"file_key": file_key, "qualname": qual, "lineno": lineno}
                current_class[file_key] = name

            elif kind == "def":
                if indent == 0:
                    qual: str = f"__functions__.{name}"
                    key: str = f"{file_key}:{qual}"
                    defs[key] = {
                        "file_key": file_key,
                        "qualname": qual,
                        "lineno": lineno,
                    }
                    current_class[file_key] = None

                elif indent == 4:
                    cls: str | None = current_class.get(file_key)
                    if cls:
                        qual: str = f"{cls}.{name}"
                        key: str = f"{file_key}:{qual}"
                        defs[key] = {
                            "file_key": file_key,
                            "qualname": qual,
                            "lineno": lineno,
                        }

    return defs


# ===============================
# 参照されている定義一覧
# ===============================


def load_used_definitions() -> set[str]:
    """
    reference_report.html 生成時の JSON 構造を再利用せず、
    build_reference_report.py と同じロジックで生成された
    by_target のキー集合を想定。
    ここでは definition_map.json から安全に再構築する。
    """
    # 実際には build_reference_report.py 実行後、
    # by_target.keys() を JSON 保存しても良い
    # 今回は「HTML からは拾わない」方針にする

    # 👉 シンプルに:
    # reference_report.py を import しても良いが、
    # 今日は「設計理解優先」で進める

    used: set[str] = set()

    # 今回は「呼ばれている定義」を reference_report.html からは取らず、
    # build_reference_report.py 実行時に保存された
    # by_target 相当の JSON がある前提にするとベスト。
    # ただし、黒川さんの環境ではまだ無いので、
    # 次回の改善ポイントとしてここは空実装にしておく。

    return used


# ===============================
# HTML 出力
# ===============================


def render_html(unused: dict[str, dict[str, Any]]) -> str:
    """未参照定義一覧 HTML 生成"""
    by_file: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for info in unused.values():
        by_file[info["file_key"]].append(info)

    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="ja">')
    parts.append('<meta charset="utf-8">')
    parts.append("<title>Unused Definitions</title>")
    parts.append("<body>")
    parts.append("<h1>参照されていない定義一覧</h1>")

    for file_key, items in sorted(by_file.items()):
        parts.append(f"<h2><code>{html.escape(file_key)}</code></h2>")
        parts.append("<ul>")
        for d in sorted(items, key=lambda x: x["lineno"]):
            link: str = vscode_link(d["file_key"], d["lineno"])
            parts.append(
                f"<li><a href='{html.escape(link)}'>"
                f"{html.escape(d['qualname'])} (line {d['lineno']})</a></li>"
            )
        parts.append("</ul>")

    parts.append("</body></html>")
    return "\n".join(parts)


# ===============================
# main
# ===============================
def main() -> None:
    """未参照定義レポート生成"""
    all_defs: Dict[str, Dict[str, str | int]] = load_all_definitions()

    # ※ 今回は「未参照 = 全定義」として動作確認用
    # 次回：used_defs を by_target JSON から読み込む
    used_defs: set[str] = load_used_definitions()

    unused: Dict[str, Dict[str, str | int]] = {
        k: v for k, v in all_defs.items() if k not in used_defs
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_text: str = render_html(unused)
    OUT_HTML.write_text(html_text, encoding="utf-8")

    # ★ 使用中定義を JSON 保存（追加）
    USED_JSON: Path = OUT_DIR / "used_definitions.json"
    used_defs_list: List[str] = sorted(used_defs)
    USED_JSON.write_text(
        json.dumps(used_defs_list, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("OK: reference report generated")
    print(OUT_HTML)
    print(f"Used definitions JSON: {USED_JSON}")
    print(f"Used count: {len(used_defs_list)}")


if __name__ == "__main__":
    main()
# End of file
