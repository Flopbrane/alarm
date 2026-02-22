# -*- coding: utf-8 -*-
#########################
# Author: F.Kurokawa
# Description:
# 「参照元（どこから呼ばれている）」「参照先（どこで定義されている）」を突き合わせ
#########################
"""
build_reference_report.py

目的:
- definition_map.json（定義マップ） + definition_map.csv（定義位置）を使って
- プロジェクト配下の .py をスキャンし
- 「参照元（どこから呼ばれている）」「参照先（どこで定義されている）」を突き合わせ
- クリック可能なHTMLレポートを1枚生成する

注意（重要）:
- Pythonは動的言語なので「完全な呼び出し解決」は不可能です。
- 本ツールは「文字列ベース + 定義マップ」で、混乱を減らすための実用ツールです。
  (obj.method() の obj が何型か、などは追いません。Class.method() は強い)

出力:
- contents_class_def/reference_report/reference_report.html
"""
from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ===============================
# ★ 設定（黒川さん環境）
# ===============================

# プロジェクトルート（固定。汎用化したい場合は下のコメント解除）
PROJECT_ROOT: Path = Path(r"D:\PC\Python\alarm").resolve()

# 汎用化する場合（別プロジェクトで使う）
# PROJECT_ROOT = Path(__file__).resolve().parent.parent

SCRIPT_DIR: Path = Path(__file__).resolve().parent
DEF_DIR: Path= SCRIPT_DIR / "definition_map"
DEF_JSON: Path = DEF_DIR / "definition_map.json"
DEF_CSV: Path = DEF_DIR / "definition_map.csv"

OUT_DIR: Path = SCRIPT_DIR / "reference_report"
OUT_HTML: Path = OUT_DIR / "reference_report.html"
EXCLUDE_DIR_NAMES: Set[str] = {
    "venv",
    ".venv",
    "__pycache__",
    "backup",
    "sound",
    ".git",
    ".github",
    ".ruff_cache",
    ".vscode",
    ".deprecated",
    "call_index_out", # 解析結果保存フォルダ
    "contents_class_def", # 自分自身を除外
    "venv-alarm312", # 仮想環境実行用Pythonがある場合
}

# 解析のノイズになりがちな組み込み/キーワード（必要に応じて追加）
IGNORE_CALL_NAMES: Set[str] = {
    "print", "len", "range", "list", "dict", "set", "tuple", "int", "str", "float", "bool",
    "min", "max", "sum", "sorted", "open", "enumerate", "zip", "map", "filter",
    "isinstance", "issubclass", "getattr", "setattr", "hasattr",
}

# 正規表現（raw文字列で警告回避）
RE_CALL_DOTTED: re.Pattern[str] = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )
RE_CALL_SIMPLE: re.Pattern[str] = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


# ===============================
# データ構造
# ===============================

@dataclass(frozen=True)
class DefLoc:
    """定義位置情報"""
    file_key: str       # utils/x.py のような相対キー
    lineno: int
    kind: str           # "def" / "class"
    qualname: str       # "__functions__.foo" or "Class.method" or "Class"


@dataclass(frozen=True)
class RefHit:
    """参照ヒット情報"""
    caller_file_key: str
    caller_lineno: int
    line_text: str
    resolved_targets: List[str]   # "file_key:qualname" のような候補（複数の場合あり）


# ===============================
# ユーティリティ
# ===============================

def is_excluded(path: Path) -> bool:
    """除外ディレクトリに含まれるか？"""
    parts: Set[str] = {p.lower() for p in path.parts}
    for x in EXCLUDE_DIR_NAMES:
        if x.lower() in parts:
            return True
    return False


def rel_key(abs_path: Path) -> str:
    """PROJECT_ROOT基準の dir/filename.py キーへ"""
    r: Path = abs_path.relative_to(PROJECT_ROOT)
    return str(r).replace("\\", "/")


def vscode_link(abs_path: Path, lineno: int) -> str:
    """VSCode で開くリンクを生成"""
    uri: str = str(abs_path).replace("\\", "/")
    return f"vscode://file/{uri}:{lineno}"


def file_abs_from_key(file_key: str) -> Path:
    """file_key から絶対パスを得る"""
    return (PROJECT_ROOT / file_key).resolve()


def safe_read_text(p: Path) -> str:
    """テキストファイルを安全に読む（エンコーディング自動判定）"""
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="cp932", errors="replace")


def strip_comment_simple(line: str) -> str:
    """
    雑に # 以降をコメントとして落とす。
    （文字列リテラル内の # は正確に判定しないが、実務用途では十分）
    """
    if "#" in line:
        return line.split("#", 1)[0]
    return line


def sort_key_by_definition(item: tuple[str, list[RefHit]]) -> tuple[str, int, str]:
    """定義キー + 参照元数降順 + 定義名 でソートするキーを返す"""
    target_key, hits = item
    if ":" in target_key:
        file_key, qual = target_key.split(":", 1)
    else:
        file_key, qual = target_key, ""
    return (file_key.lower(), -len(hits), qual.lower())


# ===============================
# 定義マップ読み込み（JSON + CSV）
# ===============================

def load_definition_map() -> Dict[str, Dict[str, List[str]]]:
    """definition_map.json を読む。"""
    if not DEF_JSON.exists():
        raise FileNotFoundError(f"definition_map.json not found: {DEF_JSON}")
    with DEF_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_definition_locations() -> Dict[str, DefLoc]:
    """
    CSVから「定義→位置」を作る。
    キーは "file_key:qualname" 形式で一意にする。
    """
    if not DEF_CSV.exists():
        raise FileNotFoundError(f"definition_map.csv not found: {DEF_CSV}")

    locs: Dict[str, DefLoc] = {}

    # CSVヘッダのBOM/クォート対策
    with DEF_CSV.open(encoding="utf-8-sig") as f:
        reader: csv.DictReader[str] = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [
                h.replace('"', "").replace("\ufeff", "").strip() for h in reader.fieldnames]

        current_class: Dict[str, Optional[str]] = {}

        for row in reader:
            file_key: str | Any = row["file_key"]
            kind: str | Any = row["kind"]
            name: str | Any = row["name"]
            lineno: int = int(row["lineno"])
            indent: int = int(row["indent"])

            if file_key not in current_class:
                current_class[file_key] = None

            if kind == "class" and indent == 0:
                # クラス定義
                qual: str | Any = name
                k: str = f"{file_key}:{qual}"
                locs[k] = DefLoc(file_key=file_key, lineno=lineno, kind="class", qualname=qual)
                current_class[file_key] = name

            elif kind == "def":
                if indent == 0:
                    # グローバル関数
                    qual = f"__functions__.{name}"
                    k = f"{file_key}:{qual}"
                    locs[k] = DefLoc(file_key=file_key, lineno=lineno, kind="def", qualname=qual)
                    current_class[file_key] = None

                elif indent == 4:
                    # クラスメソッド
                    cls: str | None = current_class.get(file_key)
                    if cls:
                        qual = f"{cls}.{name}"
                        k = f"{file_key}:{qual}"
                        locs[k] = DefLoc(
                            file_key=file_key,
                            lineno=lineno,
                            kind="def",
                            qualname=qual)
                else:
                    # 内部関数は今回は無視（必要なら後で扱う）
                    pass

    return locs


def build_symbol_index(
    def_map: Dict[str, Dict[str, List[str]]]
    ) -> Tuple[Set[str], Set[str], Set[str], Dict[str, List[str]]]:
    """
    参照解決のための索引を作る:
    - global_funcs: foo
    - classes: ClassName
    - class_methods_full: Class.method
    - method_name_to_targets: method -> [ "file:Class.method", ... ]（曖昧対策）
    """
    global_funcs: Set[str] = set()
    classes: Set[str] = set()
    class_methods_full: Set[str] = set()
    method_name_to_targets: Dict[str, List[str]] = {}

    for file_key, items in def_map.items():
        # functions
        for fn in items.get("__functions__", []):
            global_funcs.add(fn)

        # classes + methods
        for cls, methods in items.items():
            if cls == "__functions__":
                continue
            classes.add(cls)
            for m in methods:
                full: str = f"{cls}.{m}"
                class_methods_full.add(full)
                method_name_to_targets.setdefault(m, []).append(f"{file_key}:{full}")

    return global_funcs, classes, class_methods_full, method_name_to_targets


# ===============================
# 参照元解析（文字列ベース）
# ===============================

def collect_py_files() -> List[Path]:
    """プロジェクト配下の .py ファイルを集める"""
    files: List[Path] = []
    for p in PROJECT_ROOT.rglob("*.py"):
        if is_excluded(p):
            continue
        files.append(p)
    return files


def resolve_call_to_targets(
    call_name: str,
    dotted_left: Optional[str],
    dotted_right: Optional[str],
    def_map: Dict[str, Dict[str, List[str]]],
    global_funcs: Set[str],
    classes: Set[str],
    class_methods_full: Set[str],
    method_name_to_targets: Dict[str, List[str]],
) -> List[str]:
    """
    呼び出し文字列から「定義先候補」を返す。
    返り値は ["file_key:qualname", ...] の形。
    """
    targets: List[str] = []

    # dotted: Instance_A.Method_B(
    if dotted_left and dotted_right:
        # Class.method() の場合（強い）
        if dotted_left in classes:
            full = f"{dotted_left}.{dotted_right}"
            if full in class_methods_full:
                # 定義先ファイルを探す（複数ファイルに同名クラスがある場合は複数になる）
                for fk, items in def_map.items():
                    if dotted_left in items and dotted_right in items[dotted_left]:
                        targets.append(f"{fk}:{full}")
                return targets

        # self.method() は型不明なので method 名だけで候補列挙（弱い）
        if dotted_left == "self":
            if dotted_right in method_name_to_targets:
                return method_name_to_targets[dotted_right][:]

        # obj.method() も型不明、弱いが候補を出す（必要なら）
        if dotted_right in method_name_to_targets:
            return method_name_to_targets[dotted_right][:]

        return []

    # simple: FunctionName_foo(
    if call_name in IGNORE_CALL_NAMES:
        return []

    if call_name in global_funcs:
        # グローバル関数の定義先（複数ファイルに同名関数があると複数）
        for fk, items in def_map.items():
            if call_name in items.get("__functions__", []):
                targets.append(f"{fk}:__functions__.{call_name}")
        return targets

    # 単純名がメソッド名だけに一致するケース（弱い）
    if call_name in method_name_to_targets:
        return method_name_to_targets[call_name][:]

    return []


def scan_references(
    def_map: Dict[str, Dict[str, List[str]]]
    ) -> Tuple[Dict[str, List[RefHit]], Dict[str, List[RefHit]]]:
    """
    参照を集める。
    - by_target: "file_key:qualname" -> [RefHit...]
    - by_caller: "caller_file_key" -> [RefHit...]
    """
    global_funcs, classes, class_methods_full, method_name_to_targets = build_symbol_index(def_map)

    by_target: Dict[str, List[RefHit]] = {}
    by_caller: Dict[str, List[RefHit]] = {}

    py_files: List[Path] = collect_py_files()

    for py in py_files:
        fk: str = rel_key(py)
        src: List[str] = safe_read_text(py).splitlines()

        for i, line in enumerate(src, start=1):
            raw: str = line.rstrip("\n")
            s: str = strip_comment_simple(raw)

            # dotted calls first
            for m in RE_CALL_DOTTED.finditer(s):
                left, right = m.group(1), m.group(2)
                targets: List[str] = resolve_call_to_targets(
                    call_name="",
                    dotted_left=left,
                    dotted_right=right,
                    def_map=def_map,
                    global_funcs=global_funcs,
                    classes=classes,
                    class_methods_full=class_methods_full,
                    method_name_to_targets=method_name_to_targets,
                )
                if targets:
                    hit = RefHit(
                        caller_file_key=fk,
                        caller_lineno=i,
                        line_text=raw.strip(),
                        resolved_targets=targets)
                    by_caller.setdefault(fk, []).append(hit)
                    for t in targets:
                        by_target.setdefault(t, []).append(hit)

            # simple calls
            for m in RE_CALL_SIMPLE.finditer(s):
                name: str | Any = m.group(1)
                # dotted の left で拾われるもの（obj.method）の "method(" もここで拾うので、
                # こちらは簡易フィルタで落とす（直前が '.' の場合）
                idx: int = m.start(1)
                if idx > 0 and s[idx - 1] == ".":
                    continue

                targets = resolve_call_to_targets(
                    call_name=name,
                    dotted_left=None,
                    dotted_right=None,
                    def_map=def_map,
                    global_funcs=global_funcs,
                    classes=classes,
                    class_methods_full=class_methods_full,
                    method_name_to_targets=method_name_to_targets,
                )
                if targets:
                    hit = RefHit(
                        caller_file_key=fk,
                        caller_lineno=i,
                        line_text=raw.strip(),
                        resolved_targets=targets)
                    by_caller.setdefault(fk, []).append(hit)
                    for t in targets:
                        by_target.setdefault(t, []).append(hit)

    return by_target, by_caller


# ===============================
# HTML出力
# ===============================

def render_html(def_map: Dict[str, Dict[str, List[str]]],
                def_locs: Dict[str, DefLoc],
                by_target: Dict[str, List[RefHit]],
                by_caller: Dict[str, List[RefHit]]) -> str:
    """
    1枚HTMLにまとめる。
    """
    # use def_map so the argument passed from main is actually used (avoids unused-argument warning)
    try:
        _def_map_count: int = len(def_map)
    except (TypeError, AttributeError):
        _def_map_count: int = 0

    def def_link_of(target_key: str) -> str:
        # target_key: "file_key:qualname"
        loc: DefLoc | None = def_locs.get(target_key)
        if not loc:
            return ""
        abs_path: Path = file_abs_from_key(loc.file_key)
        return vscode_link(abs_path, loc.lineno)

    def def_label(target_key: str) -> str:
        return target_key

    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="ja">')
    parts.append('<meta charset="utf-8">')
    parts.append("<title>Alarm Reference Report</title>")
    parts.append("""
    <style>
    body { font-family: sans-serif; padding: 12px; }
    input { width: 420px; padding: 6px 8px; }
    table { border-collapse: collapse; width: 100%; margin-top: 10px; }
    th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
    th { position: sticky; top: 0; background: #f7f7f7; }
    code { background: #f5f5f5; padding: 0.05em 0.25em; border-radius: 4px; }
    .small { color: #666; font-size: 0.9em; }
    details { margin: 6px 0; }
    summary { cursor: pointer; }
    </style>
    <script>
    function filterRows() {
    const q = document.getElementById("q").value.toLowerCase();
    const rows = document.querySelectorAll("tr.data");
    rows.forEach(r => {
        const t = r.innerText.toLowerCase();
        r.style.display = t.includes(q) ? "" : "none";
    });
    }
    </script>
    """)
    parts.append("<body>")
    parts.append("<h1>Alarm Reference Report</h1>")
    parts.append(
        f"<p class='small'>PROJECT_ROOT: <code>{html.escape(str(PROJECT_ROOT))}</code></p>")
    parts.append(
        "<p class='small'>検索: <input id='q' oninput='filterRows()' placeholder='例: ConfigManager / save_config / utils/'></p>")

    # ---- 定義→参照元 -------------
    parts.append("<h2>定義 → 参照元（呼ばれている場所）</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Definition</th><th>Defined At</th><th>Callers</th></tr>")

    # sort targets by caller count desc
    for target_key, hits in sorted(
        by_target.items(), key=sort_key_by_definition, reverse=False
    ):
        def_url: str = def_link_of(target_key)
        def_cell: str = f"<code>{html.escape(def_label(target_key))}</code>"
        at_cell = "-"
        if def_url:
            at_cell: str = f"<a href='{html.escape(def_url)}'>VS Code</a>"

        # callers list
        items: List[str] = []
        for h in hits[:200]:  # 1定義あたり表示上限
            abs_path: Path = file_abs_from_key(h.caller_file_key)
            url: str = vscode_link(abs_path, h.caller_lineno)
            items.append(
                f"<li><a href='{html.escape(url)}'><code>{html.escape(h.caller_file_key)}:{h.caller_lineno}</code></a> "
                f"<span class='small'>{html.escape(h.line_text)}</span></li>"
            )
        caller_html: str = "<details><summary>" + f"{len(hits)} hit(s)</summary><ul>" + "\n".join(items) + "</ul></details>"

        parts.append(f"<tr class='data'><td>{def_cell}</td><td>{at_cell}</td><td>{caller_html}</td></tr>")

    parts.append("</table>")

    # ---- 参照元→参照先 -------------
    parts.append("<h2>参照元 → 参照先（このファイルが呼んでいる定義）</h2>")
    parts.append("<table>")
    parts.append("<tr><th>Caller file</th><th>Hits</th></tr>")

    for caller_file, hits in sorted(by_caller.items(), key=lambda x: len(x[1]), reverse=True):
        # summarize targets
        summary: Dict[str, int] = {}
        for h in hits:
            for t in h.resolved_targets:
                summary[t] = summary.get(t, 0) + 1

        # make detail list
        det_lines: List[str] = []
        for t, cnt in sorted(summary.items(), key=lambda x: x[1], reverse=True)[:200]:
            def_url = def_link_of(t)
            label: str = html.escape(t)
            if def_url:
                det_lines.append(f"<li><a href='{html.escape(def_url)}'><code>{label}</code></a> : {cnt}</li>")
            else:
                det_lines.append(f"<li><code>{label}</code> : {cnt}</li>")

        caller_cell: str = f"<code>{html.escape(caller_file)}</code>"
        detail: str = "<details><summary>" + f"{len(hits)} hit(s)</summary><ul>" + "\n".join(det_lines) + "</ul></details>"
        parts.append(f"<tr class='data'><td>{caller_cell}</td><td>{detail}</td></tr>")

    parts.append("</table>")

    parts.append("<p class='small'>注意: obj.method() / getattr / import alias などは推定が難しいため、候補扱い or 未検出になる場合があります。</p>")
    parts.append("</body></html>")
    return "\n".join(parts)


def main() -> None:
    """参照スキャンレポート生成"""
    if not DEF_JSON.exists():
        raise FileNotFoundError(f"Missing: {DEF_JSON}")
    if not DEF_CSV.exists():
        raise FileNotFoundError(f"Missing: {DEF_CSV}")

    def_map: Dict[str, Dict[str, List[str]]] = load_definition_map()
    def_locs: Dict[str, DefLoc] = load_definition_locations()

    by_target: Dict[str, List[RefHit]]
    by_caller: Dict[str, List[RefHit]]
    by_target, by_caller = scan_references(def_map)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    html_text: str = render_html(def_map, def_locs, by_target, by_caller)
    OUT_HTML.write_text(html_text, encoding="utf-8")

    print("OK: reference report generated")
    print(OUT_HTML)


if __name__ == "__main__":
    main()
