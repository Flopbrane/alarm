from __future__ import annotations
"""どのファイルのどの関数で、何処の関数が呼ばれているかを調査するユーティリティ"""
# pyright: reportGeneralTypeIssues=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownArgumentType=false
# -*- coding: utf-8 -*-
#########################
# Author: F.Kurokawa
# Description:
# どのファイルのどの関数で、何処の関数が呼ばれているかを調査するユーティリティ
#########################
"""build_call_index.py
Python AST で「関数/メソッド → 呼び出し名」を抽出し、CSV/HTMLに出力する。

- 解析対象: project_root 以下の .py
- 除外: venv/.venv/__pycache__/backup/sound/.git/.github など（必要なら追加）
- 出力: output_dir に call_index.csv / call_index.html

注意:
- Pythonは動的言語なので「完全な呼び出し解決」はできません。
  ここで出すのは「見えている呼び出し名の一覧（実務で十分役立つ）」です。"""

import ast
import csv
import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ==========================
# 設定（黒川さんの環境向け）
# ==========================
# 探索層の基準設定
MAX_DEPTH = 5

# この .py が置かれているフォルダ（contents_class_def）を基準にする
SCRIPT_DIR: Path = Path(__file__).resolve().parent

# プロジェクトのルート: contents_class_def の1つ上（D:\PC\Python\alarm）
PROJECT_ROOT: Path = SCRIPT_DIR

# PowerShellで作った「ファイル別HTML」置き場（必要なら変更）
# 例: contents_class_def/html_index に出ている想定
PS_HTML_DIR: Path = (SCRIPT_DIR / "html_index").resolve()

# 出力先
OUTPUT_DIR: Path = PROJECT_ROOT / "call_index_out"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# 除外したいフォルダ名（必要に応じて増やしてOK）
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
    "venv-alarm312",
    "contents_class_def",  # 自分自身を除外
}

# ==========================
# 実装
# ==========================
@dataclass(frozen=True)
class FuncRow:
    """関数ごとの呼び出し情報行"""
    file: str
    qualname: str
    lineno: int
    calls: str
    vscode_link: str
    ps_html_link: str

# ==========================
def is_excluded(path: Path) -> bool:
    """除外フォルダに含まれるか判定"""
    parts: Set[str] = {p.lower() for p in path.parts}
    for x in EXCLUDE_DIR_NAMES:
        if x.lower() in parts:
            return True
    return False


def collect_py_files(root: Path) -> List[Path]:
    """root 以下の .py ファイルを収集（除外フォルダをスキップ）"""
    files: List[Path] = []
    for p in root.rglob("*.py"):
        if is_excluded(p):
            continue
        files.append(p)
    return files


def dotted_name(expr: ast.AST) -> Optional[str]:
    """Callのnode.funcから、可能なら foo / obj.bar / pkg.mod.func のような名前を作る"""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        left: str | None = dotted_name(expr.value)
        if left:
            return f"{left}.{expr.attr}"
        return expr.attr
    return None


def parse_import_aliases(tree: ast.AST) -> Dict[str, str]:
    """
    import / from import の alias をざっくり解決する。
    例:
      import utils as u -> {"u": "utils"}
      from utils import foo as f -> {"f": "utils.foo"}
    """
    alias_map: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    alias_map[a.asname] = a.name
        elif isinstance(node, ast.ImportFrom):
            mod: str = node.module or ""
            for a in node.names:
                if a.asname:
                    alias_map[a.asname] = f"{mod}.{a.name}" if mod else a.name
    return alias_map


class CallCollector(ast.NodeVisitor):
    """関数/メソッドごとの呼び出し名を収集するAST Visitor"""
    def __init__(self, alias_map: Dict[str, str]) -> None:
        self.alias_map: Dict[str, str] = alias_map
        self.class_stack: List[str] = []
        self.func_stack: List[Tuple[str, int]] = []  # (qualname, lineno)
        self.calls_by_func: Dict[Tuple[str, int], Set[str]] = {}
        self.depth: int = 0

    # ★ ここに置く（最重要）
    def visit(self, node: ast.AST) -> None:
        if self.depth >= MAX_DEPTH:
            return  # これ以上潜らない

        self.depth += 1
        super().visit(node)
        self.depth -= 1

    def current_func_key(self) -> Optional[Tuple[str, int]]:
        """現在の関数/メソッドのキーを取得（なければ None）"""
        if not self.func_stack:
            return None
        return self.func_stack[-1]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """クラス定義に入る"""
        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """関数/メソッド定義に入る"""
        self._enter_func(node)
        self.generic_visit(node)
        self._exit_func()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """非同期関数/メソッド定義に入る"""
        self._enter_func(node)
        self.generic_visit(node)
        self._exit_func()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return  # 潜らない
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        return

    def _enter_func(self, node: ast.AST) -> None:
        """関数/メソッド定義に入る（内部処理）"""
        # Safely obtain name and lineno and normalize types to (str, int)
        raw_name: Any | str = getattr(node, "name", "<func>")
        if isinstance(raw_name, str):
            name: str = raw_name
        else:
            name = str(raw_name)

        raw_lineno: Any | int = getattr(node, "lineno", 1)
        try:
            lineno = int(raw_lineno)
        except Exception:
            lineno = 1

        if self.class_stack:
            qual: str = ".".join(self.class_stack + [name])
        else:
            qual = name
        key: Tuple[str, int] = (qual, lineno)
        self.func_stack.append(key)
        self.calls_by_func.setdefault(key, set())

    def _exit_func(self) -> None:
        """関数/メソッド定義から出る（内部処理）"""
        self.func_stack.pop()

    def visit_Call(self, node: ast.Call) -> None:
        """関数/メソッド呼び出しを処理"""
        key: Optional[Tuple[str, int]] = self.current_func_key()
        if key is None:
            return

        name: str | None = dotted_name(node.func)
        if name:
            head: str = name.split(".")[0]
            if head in self.alias_map:
                resolved: str = self.alias_map[head]
                rest = ".".join(name.split(".")[1:])
                name = f"{resolved}.{rest}" if rest else resolved

            if name.startswith("self.") and self.class_stack:
                name = f"{self.class_stack[-1]}.{name[5:]}"

            self.calls_by_func[key].add(name)

        # 深掘りしない（重要）
        # self.generic_visit(node)


def vscode_file_link(file_path: Path, lineno: int) -> str:
    """VS Code で該当ファイルの該当行を開くリンクを作成"""
    # VS Code URI はスラッシュ区切り
    uri: str = str(file_path.resolve()).replace("\\", "/")
    return f"vscode://file/{uri}:{lineno}"


def ps_html_link_for_py(py_path: Path) -> str:
    """
    PowerShell側のファイル別HTMLにリンクする。
    例: alarm_model.py -> alarm_model.html
    見つからなければ空文字。
    """
    html_name: str = py_path.stem + ".html"
    candidate: Path = PS_HTML_DIR / html_name
    if candidate.exists():
        return candidate.as_uri()
    return ""


def main() -> None:
    """メイン処理"""
    sys.setrecursionlimit(5000)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("SCRIPT_DIR :", SCRIPT_DIR)
    print("PROJECT_ROOT:", PROJECT_ROOT)
    py_files: List[Path] = collect_py_files(PROJECT_ROOT)
    print("PY FILE COUNT:", len(py_files))
    rows: List[FuncRow] = []

    for py in py_files:
        try:
            src = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # まれにcp932等が混ざる場合の保険
            src: str = py.read_text(encoding="cp932", errors="replace")

        try:
            tree: ast.Module = ast.parse(src)
        except SyntaxError:
            # 編集途中で壊れているファイルはスキップ（必要ならログ化）
            continue

        alias_map: Dict[str, str] = parse_import_aliases(tree)
        collector = CallCollector(alias_map)
        collector.visit(tree)

        rel = str(py.relative_to(PROJECT_ROOT))

        for (qual, lineno), calls_set in sorted(
            collector.calls_by_func.items(), key=lambda x: (x[0][0], x[0][1])
        ):
            calls_sorted: List[str] = sorted(calls_set)
            calls_str: str = ", ".join(calls_sorted)

            rows.append(
                FuncRow(
                    file=rel,
                    qualname=qual,
                    lineno=lineno,
                    calls=calls_str,
                    vscode_link=vscode_file_link(py, lineno),
                    ps_html_link=ps_html_link_for_py(py),
                )
            )

    # CSV出力
    csv_path: Path = OUTPUT_DIR / "call_index.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "qualname", "lineno", "calls"])
        for r in rows:
            w.writerow([r.file, r.qualname, r.lineno, r.calls])

    # HTML出力（一覧）
    html_path: Path = OUTPUT_DIR / "call_index.html"
    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="ja">')
    parts.append('<meta charset="utf-8">')
    parts.append("<title>Call Index (AST)</title>")
    parts.append(
        """
<style>
body { font-family: sans-serif; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
th { position: sticky; top: 0; background: #f7f7f7; }
code { background: #f5f5f5; padding: 0.05em 0.25em; border-radius: 4px; }
.small { color: #666; font-size: 0.9em; }
</style>
"""
    )
    parts.append("<body>")
    parts.append("<h1>Call Index (AST)</h1>")
    parts.append(
        f"<p class='small'>対象: {html.escape(str(PROJECT_ROOT))} / 出力: {html.escape(str(OUTPUT_DIR))}</p>"
    )
    parts.append("<table>")
    parts.append(
        "<tr><th>File</th><th>Function</th><th>Calls (detected)</th><th>Links</th></tr>"
    )

    for r in rows:
        file_html: str = html.escape(r.file)
        func_html: str = html.escape(f"{r.qualname} (L{r.lineno})")
        calls_html: str = html.escape(r.calls)

        links: List[str] = []
        links.append(f"<a href='{html.escape(r.vscode_link)}'>VS Code</a>")
        if r.ps_html_link:
            links.append(f"<a href='{html.escape(r.ps_html_link)}'>PS HTML</a>")
        links_html: str = " / ".join(links)

        parts.append(
            f"<tr>"
            f"<td><code>{file_html}</code></td>"
            f"<td><code>{func_html}</code></td>"
            f"<td>{calls_html}</td>"
            f"<td>{links_html}</td>"
            f"</tr>"
        )

    parts.append("</table>")
    parts.append(
        "<p class='small'>注意: import alias / self.* の一部は推定で解決します。動的呼び出し（getattr等）は拾えません。</p>"
    )
    parts.append("</body></html>")

    html_path.write_text("\n".join(parts), encoding="utf-8")

    print("OK:")
    print(f"  CSV : {csv_path}")
    print(f"  HTML: {html_path}")


if __name__ == "__main__":
    main()
