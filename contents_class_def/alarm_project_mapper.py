# -*- coding: utf-8 -*-
# pylint: disable=invalid-name
"""
alarm_project_mapper.py

Alarm プロジェクト専用の解析ツール。
特に manager / gui の分割前確認に使うことを目的に、以下を生成する。

生成物:
- analysis_out/index.html
- analysis_out/file_dependencies.html
- analysis_out/alarm_manager_temp_internal_map.html
- analysis_out/gui_internal_map.html
- analysis_out/alarm_manager_temp_split_hints.html
- analysis_out/gui_split_hints.html
- analysis_out/analysis_summary.json

主な解析内容:
1) import 依存（上流 / 下流）
2) クラス / 関数 / メソッド定義一覧
3) ファイル内部 call graph
4) manager / gui のブロック分割ヒント
5) VS Code ジャンプリンク

設計方針:
- import / 定義 / call は AST ベース
- Python の動的性質により 100% 完全ではない
- ただし manager 分割・gui 分離の足場として使えるレベルを狙う

使い方例:
    python alarm_project_mapper.py --project-root D:\\PC\\Python\\alarm

省略時は、このスクリプトの親ディレクトリを project root 候補として使う。
"""

from __future__ import annotations

import argparse
import ast
import html
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Any

# ============================================================
# 設定
# ============================================================

DEFAULT_EXCLUDE_DIRS: set[str] = {
    "__pycache__",
    ".git",
    ".github",
    ".venv",
    "venv",
    "venv-alarm312",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
    "backup",
    "sound",
    "contents_class_def",
    "call_index_out",
    "analysis_out",
}

TARGET_FILES_DEFAULT: tuple[str, ...] = (
    "alarm_manager_temp.py",
    "gui.py",
)

HTML_STYLE = """
body {
    font-family: "Segoe UI", sans-serif;
    margin: 20px;
    line-height: 1.45;
}
h1, h2, h3 {
    margin-top: 1.2em;
}
code {
    background: #f4f4f4;
    padding: 0.1em 0.3em;
    border-radius: 4px;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin-top: 0.8em;
}
th, td {
    border: 1px solid #d8d8d8;
    padding: 6px 8px;
    vertical-align: top;
}
th {
    background: #f7f7f7;
    position: sticky;
    top: 0;
}
ul {
    margin-top: 0.4em;
}
.small {
    color: #666;
    font-size: 0.92em;
}
.box {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 12px;
    margin: 12px 0;
}
.badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background: #eef3ff;
    margin-right: 6px;
}
.warn {
    background: #fff4db;
}
.good {
    background: #e9f8ec;
}
"""

# ============================================================
# データ構造
# ============================================================


@dataclass
class ImportInfo:
    """Import 文の情報"""
    module: str
    names: list[str] = field(default_factory=lambda: [])
    alias_map: dict[str, str] = field(default_factory=lambda: {})
    lineno: int = 0
    kind: str = "import"  # import / from


@dataclass
class DefInfo:
    """関数 / クラス / メソッド定義の情報"""
    file_key: str
    qualname: str
    short_name: str
    kind: str  # class / function / method
    lineno: int
    end_lineno: int
    class_name: str | None = None
    node_type: str | None = None
    decorators: list[str] = field(default_factory=lambda: [])


@dataclass
class CallEdge:
    """関数呼び出しの情報"""
    caller: str
    callee_expr: str
    lineno: int
    resolved_to: str | None = None
    resolution_kind: str = "unresolved"


@dataclass
class FileAnalysis:
    """ファイル解析の情報"""
    path: Path
    file_key: str
    imports: list[ImportInfo] = field(default_factory=lambda: [])
    defs: dict[str, DefInfo] = field(default_factory=lambda: {})
    class_methods: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    call_edges: list[CallEdge] = field(default_factory=lambda: [])
    imported_aliases: dict[str, str] = field(default_factory=lambda: {})
    import_modules: dict[str, str] = field(default_factory=lambda: {})

@dataclass
class MethodScore:
    """関数 / メソッドのスコア情報"""
    kind: str
    lineno: int
    bucket: str
    internal_in: int
    internal_out: int
    external_hits: int
    decorators: list[str]


# ============================================================
# ユーティリティ
# ============================================================
# ユーティリティ
# ============================================================
def vscode_link(abs_path: Path, lineno: int) -> str:
    """VSCode で開くためのリンクを生成"""
    uri: str = str(abs_path.resolve()).replace("\\", "/")
    return f"vscode://file/{uri}:{lineno}"


def safe_read_text(path: Path) -> str:
    """ファイルを安全に読み込む"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp932", errors="replace")


def is_excluded(path: Path, exclude_dirs: set[str]) -> bool:
    """指定されたパスが除外ディレクトリに含まれるかを判定"""
    parts: set[str] = {p.lower() for p in path.parts}
    return any(x.lower() in parts for x in exclude_dirs)


def rel_key(project_root: Path, path: Path) -> str:
    """プロジェクトルートからの相対パスをキーとして返す"""
    return str(path.resolve().relative_to(project_root.resolve())).replace("\\", "/")


def path_to_module(file_key: str) -> str:
    """ファイルキーからモジュール名を生成"""
    p = Path(file_key)
    parts: list[str] = list(p.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def html_page(title: str, body: str) -> str:
    """HTML ページを生成"""
    return (
        "<!doctype html>\n"
        '<html lang="ja">\n'
        '<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{HTML_STYLE}</style>\n"
        f"<body><h1>{html.escape(title)}</h1>{body}</body></html>"
    )


def ensure_out_dir(project_root: Path) -> Path:
    """出力ディレクトリを作成"""
    out_dir: Path = project_root / "analysis_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def decorator_name(dec: ast.AST) -> str:
    """デコレーターの名前を取得"""
    if isinstance(dec, ast.Name):
        return dec.id
    if isinstance(dec, ast.Attribute):
        return ast.unparse(dec)
    if isinstance(dec, ast.Call):
        try:
            return ast.unparse(dec.func)
        except (ValueError, TypeError):
            return "<decorator-call>"
    try:
        return ast.unparse(dec)
    except (ValueError, TypeError):
        return "<decorator>"


def get_call_expr_name(node: ast.Call) -> tuple[str, str | None, str | None]:
    """関数呼び出し式の名前を取得"""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id, None, None
    if isinstance(func, ast.Attribute):
        try:
            expr: str = ast.unparse(func)
        except (ValueError, TypeError):
            expr = func.attr
        left: str | None = None
        if isinstance(func.value, ast.Name):
            left = func.value.id
        elif isinstance(func.value, ast.Attribute):
            try:
                left = ast.unparse(func.value)
            except (ValueError, TypeError):
                left = None
        return expr, left, func.attr
    try:
        return ast.unparse(func), None, None
    except (ValueError, TypeError):
        return "<call>", None, None


def common_prefix_bucket(name: str) -> str:
    """ゆるいブロック推定用。prefix ベースでまとめる。"""
    n = name.replace("__", "_").strip("_")
    if not n:
        return "misc"

    for prefix in (
        "load",
        "save",
        "recalc",
        "repair",
        "update",
        "mark",
        "fire",
        "stop",
        "begin",
        "build",
        "create",
        "delete",
        "remove",
        "clear",
        "notify",
        "play",
        "validate",
        "normalize",
        "serialize",
        "deserialize",
        "open",
        "close",
        "draw",
        "render",
        "refresh",
        "bind",
        "event",
        "click",
        "toggle",
        "set",
        "get",
        "apply",
        "handle",
    ):
        if n.startswith(prefix):
            return prefix

    if "phase" in n:
        return "phase"
    if "dialog" in n:
        return "dialog"
    if "button" in n:
        return "button"
    if "widget" in n:
        return "widget"
    if "tree" in n:
        return "tree"
    if "list" in n:
        return "list"
    if "config" in n:
        return "config"
    if "alarm" in n:
        return "alarm"
    if "state" in n:
        return "state"
    return n.split("_", 1)[0]


# ============================================================
# AST 解析
# ============================================================


class FileAnalyzer(ast.NodeVisitor):
    """ファイル解析クラス"""
    def __init__(self, project_root: Path, path: Path, file_key: str) -> None:
        self.project_root: Path = project_root
        self.path: Path = path
        self.file_key: str = file_key
        self.result = FileAnalysis(path=path, file_key=file_key)
        self._class_stack: list[str] = []
        self._func_stack: list[str] = []

    # -------------------- imports --------------------
    def visit_Import(self, node: ast.Import) -> None:
        """Import 文の情報を収集"""
        info = ImportInfo(module="", lineno=node.lineno, kind="import")
        for alias in node.names:
            full: str = alias.name
            as_name: str = alias.asname or full.split(".")[-1]
            info.names.append(full)
            info.alias_map[as_name] = full
            self.result.import_modules[as_name] = full
        self.result.imports.append(info)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """ImportFrom 文の情報を収集"""
        base: str = node.module or ""
        info = ImportInfo(module=base, lineno=node.lineno, kind="from")
        for alias in node.names:
            imported_name: str = alias.name
            as_name: str = alias.asname or imported_name
            full: str = f"{base}.{imported_name}" if base else imported_name
            info.names.append(imported_name)
            info.alias_map[as_name] = full
            self.result.imported_aliases[as_name] = full
        self.result.imports.append(info)
        self.generic_visit(node)

    # -------------------- defs --------------------
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """クラス定義の情報を収集"""
        qualname = node.name
        self.result.defs[qualname] = DefInfo(
            file_key=self.file_key,
            qualname=qualname,
            short_name=node.name,
            kind="class",
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            class_name=None,
            node_type=type(node).__name__,
            decorators=[decorator_name(d) for d in node.decorator_list],
        )
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """関数定義の情報を収集"""
        self._register_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """非同期関数定義の情報を収集"""
        self._register_function(node)

    def _register_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """関数 / メソッド定義の情報を登録"""
        class_name: str | None = self._class_stack[-1] if self._class_stack else None
        if class_name:
            qualname: str = f"{class_name}.{node.name}"
            kind: str = "method"
            self.result.class_methods[class_name].append(qualname)
        else:
            qualname: str = f"__functions__.{node.name}"
            kind: str = "function"

        self.result.defs[qualname] = DefInfo(
            file_key=self.file_key,
            qualname=qualname,
            short_name=node.name,
            kind=kind,
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            class_name=class_name,
            node_type=type(node).__name__,
            decorators=[decorator_name(d) for d in node.decorator_list],
        )

        self._func_stack.append(qualname)
        self.generic_visit(node)
        self._func_stack.pop()

    # -------------------- calls --------------------
    def visit_Call(self, node: ast.Call) -> None:
        """関数呼び出しの情報を収集"""
        if self._func_stack:
            caller: str = self._func_stack[-1]
            expr: str
            left: str | None
            attr: str | None
            resolved_to: str | None
            resolution_kind: str

            expr, left, attr = get_call_expr_name(node)
            resolved_to, resolution_kind = self._resolve_local_call(expr, left, attr)
            self.result.call_edges.append(
                CallEdge(
                    caller=caller,
                    callee_expr=expr,
                    lineno=node.lineno,
                    resolved_to=resolved_to,
                    resolution_kind=resolution_kind,
                )
            )
        self.generic_visit(node)

    def _resolve_local_call(
        self,
        expr: str,
        left: str | None,
        attr: str | None,
    ) -> tuple[str | None, str]:
        """ローカル関数呼び出しの解決"""
        defs: dict[str, DefInfo] = self.result.defs
        current: str = self._func_stack[-1] if self._func_stack else ""
        current_class: str | None = (
            current.split(".", 1)[0]
            if "." in current and not current.startswith("__functions__")
            else None
        )

        # self.method()
        if left == "self" and attr and current_class:
            q: str = f"{current_class}.{attr}"
            if q in defs:
                return q, "self-method"

        # cls.method()
        if left == "cls" and attr and current_class:
            q = f"{current_class}.{attr}"
            if q in defs:
                return q, "cls-method"

        # ClassName.method()
        if left and attr:
            q = f"{left}.{attr}"
            if q in defs:
                return q, "class-method"

        # simple local function call
        if expr and f"__functions__.{expr}" in defs:
            return f"__functions__.{expr}", "local-function"

        # same class method call by bare name()
        if expr and current_class and f"{current_class}.{expr}" in defs:
            return f"{current_class}.{expr}", "same-class-bare"

        return None, "unresolved"


# ============================================================
# プロジェクト全体解析
# ============================================================


def collect_py_files(project_root: Path, exclude_dirs: set[str]) -> list[Path]:
    """プロジェクト内の Python ファイルを収集"""
    files: list[Path] = []
    for p in project_root.rglob("*.py"):
        if is_excluded(p, exclude_dirs):
            continue
        files.append(p)
    return sorted(files)


def parse_file(project_root: Path, path: Path) -> FileAnalysis | None:
    """ファイルを解析して FileAnalysis を返す"""
    source: str = safe_read_text(path)
    try:
        tree: ast.Module = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        print(f"[WARN] SyntaxError skip: {path} ({e})")
        return None

    fk: str = rel_key(project_root, path)
    analyzer = FileAnalyzer(project_root=project_root, path=path, file_key=fk)
    analyzer.visit(tree)
    return analyzer.result


def analyze_project(
    project_root: Path, exclude_dirs: set[str]
) -> dict[str, FileAnalysis]:
    """プロジェクト全体を解析してファイル解析結果を返す"""
    result: dict[str, FileAnalysis] = {}
    for path in collect_py_files(project_root, exclude_dirs):
        analyzed: FileAnalysis | None = parse_file(project_root, path)
        if analyzed is not None:
            result[analyzed.file_key] = analyzed
    return result


# ============================================================
# 依存関係・解決補助
# ============================================================


def build_module_index(files: dict[str, FileAnalysis]) -> dict[str, str]:
    """module.path -> file_key"""
    out: dict[str, str] = {}
    for fk in files:
        out[path_to_module(fk)] = fk
        stem: str = Path(fk).stem
        out.setdefault(stem, fk)
    return out


def build_global_definition_index(
    files: dict[str, FileAnalysis],
) -> dict[str, list[str]]:
    """simple symbol -> [file_key:qualname]"""
    idx: dict[str, list[str]] = defaultdict(list)
    for fk, fa in files.items():
        for qual, d in fa.defs.items():
            idx[d.short_name].append(f"{fk}:{qual}")
            if d.kind == "method" and d.class_name:
                idx[f"{d.class_name}.{d.short_name}"].append(f"{fk}:{qual}")
            if d.kind == "class":
                idx[d.short_name].append(f"{fk}:{qual}")
    return idx


def downstream_imports(
    file_analysis: FileAnalysis, module_index: dict[str, str]
) -> set[str]:
    """ファイル解析結果から下流のインポート依存関係を取得"""
    deps: set[str] = set()

    for alias, mod in file_analysis.import_modules.items():
        del alias
        for candidate in (mod, mod.split(".")[0]):
            if candidate in module_index:
                deps.add(module_index[candidate])
                break

    for alias, full in file_analysis.imported_aliases.items():
        del alias
        parts: list[str] = full.split(".")
        for i in range(len(parts), 0, -1):
            candidate: str = ".".join(parts[:i])
            if candidate in module_index:
                deps.add(module_index[candidate])
                break

    deps.discard(file_analysis.file_key)
    return deps


def build_dependency_maps(
    files: dict[str, FileAnalysis],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """ファイル間の依存関係マップを構築"""
    module_index: dict[str, str] = build_module_index(files)
    down: dict[str, set[str]] = {}
    up: dict[str, set[str]] = defaultdict(set)

    for fk, fa in files.items():
        deps: set[str] = downstream_imports(fa, module_index)
        down[fk] = deps
        for dep in deps:
            up[dep].add(fk)

    for fk in files:
        up.setdefault(fk, set())
        down.setdefault(fk, set())
    return up, down


def resolve_cross_file_calls(files: dict[str, FileAnalysis]) -> None:
    """ファイル間の関数呼び出しを解決"""
    global_defs: dict[str, list[str]] = build_global_definition_index(files)

    for fk, fa in files.items():
        for edge in fa.call_edges:
            if edge.resolved_to:
                edge.resolution_kind = f"local:{edge.resolution_kind}"
                continue

            expr: str = edge.callee_expr
            # module.function / Class.method / imported name
            if expr in global_defs:
                targets: list[str] = global_defs[expr]
                if len(targets) == 1:
                    edge.resolved_to = targets[0]
                    edge.resolution_kind = "global-exact"
                    continue

            if "." in expr:
                right: str = expr.split(".")[-1]
                if expr in global_defs and len(global_defs[expr]) == 1:
                    edge.resolved_to = global_defs[expr][0]
                    edge.resolution_kind = "global-dotted"
                    continue
                if right in global_defs and len(global_defs[right]) == 1:
                    edge.resolved_to = global_defs[right][0]
                    edge.resolution_kind = "global-right-only"
                    continue

            # imported alias
            if expr in fa.imported_aliases:
                imported: str = fa.imported_aliases[expr]
                if imported in global_defs and len(global_defs[imported]) == 1:
                    edge.resolved_to = global_defs[imported][0]
                    edge.resolution_kind = "imported-alias"


def build_internal_edges(file_analysis: FileAnalysis) -> dict[str, list[CallEdge]]:
    """ファイル内の関数呼び出しエッジを構築"""
    out: dict[str, list[CallEdge]] = defaultdict(list)
    internal_defs: set[str] = set(file_analysis.defs)
    for edge in file_analysis.call_edges:
        if (
            edge.resolved_to
            and ":" not in edge.resolved_to
            and edge.resolved_to in internal_defs
        ):
            out[edge.caller].append(edge)
        elif edge.resolved_to and edge.resolved_to.startswith(
            f"{file_analysis.file_key}:"
        ):
            qual: str = edge.resolved_to.split(":", 1)[1]
            if qual in internal_defs:
                out[edge.caller].append(
                    CallEdge(
                        caller=edge.caller,
                        callee_expr=edge.callee_expr,
                        lineno=edge.lineno,
                        resolved_to=qual,
                        resolution_kind=edge.resolution_kind,
                    )
                )
    return out


def build_cross_file_usage(
    files: dict[str, FileAnalysis], target_file_key: str
) -> dict[str, list[CallEdge]]:
    """ファイル間の関数呼び出し使用状況を構築"""
    usage: dict[str, list[CallEdge]] = defaultdict(list)
    prefix: str = f"{target_file_key}:"
    for fk, fa in files.items():
        if fk == target_file_key:
            continue
        for edge in fa.call_edges:
            if edge.resolved_to and edge.resolved_to.startswith(prefix):
                usage[edge.resolved_to.split(":", 1)[1]].append(edge)
    return usage


# ============================================================
# 分割ヒント
# ============================================================


def build_split_hints(
    file_analysis: FileAnalysis, cross_usage: dict[str, list[CallEdge]]
) -> dict[str, object]:
    """分割ヒントを構築"""
    internal_edges: dict[str, list[CallEdge]] = build_internal_edges(file_analysis)
    defs: dict[str, DefInfo] = file_analysis.defs

    method_scores: dict[str, MethodScore] = {}
    buckets: dict[str, list[str]] = defaultdict(list)

    for qual, info in defs.items():
        if info.kind not in {"method", "function"}:
            continue
        out_calls: int = len(internal_edges.get(qual, []))
        in_calls = 0
        for caller, edges in internal_edges.items():
            for e in edges:
                target: str | None = e.resolved_to
                if target == qual:
                    in_calls += 1
        external_hits: int = len(cross_usage.get(qual, []))
        bucket: str = common_prefix_bucket(info.short_name)
        buckets[bucket].append(qual)
        method_scores[qual] = MethodScore(
            kind=info.kind,
            lineno=info.lineno,
            bucket=bucket,
            internal_in=in_calls,
            internal_out=out_calls,
            external_hits=external_hits,
            decorators=info.decorators,
        )

    # 外部から使われるもの = public 候補
    public_surface: list[str] = sorted(
        [q for q, s in method_scores.items() if int(s.external_hits) > 0],
        key=lambda q: (
            -(int(method_scores[q].external_hits)),
            int(method_scores[q].lineno),
        ),
    )

    heavy_nodes: list[str] = sorted(
        method_scores,
        key=lambda q: (
            -(
                int(method_scores[q].internal_in)
                + int(method_scores[q].internal_out)
                + int(method_scores[q].external_hits)
            ),
            int(method_scores[q].lineno),
        ),
    )

    ordered_buckets: list[tuple[str, list[str]]] = sorted(
        buckets.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )

    return {
        "method_scores": method_scores,
        "public_surface": public_surface,
        "heavy_nodes": heavy_nodes,
        "buckets": {
            k: sorted(v, key=lambda q: defs[q].lineno) for k, v in ordered_buckets
        },
    }


# ============================================================
# HTML レンダリング
# ============================================================


def render_file_dependencies(
    project_root: Path,
    files: dict[str, FileAnalysis],
    up_map: dict[str, set[str]],
    down_map: dict[str, set[str]],
    targets: Iterable[str],
) -> str:
    """ファイル依存関係を HTML でレンダリング"""
    body: list[str] = []
    body.append(
        f"<p class='small'>PROJECT_ROOT: <code>{html.escape(str(project_root))}</code></p>"
    )
    body.append(
        "<div class='box'><b>見方:</b> 上流 = このファイルを import している側 / 下流 = このファイルが import している側</div>"
    )

    for fk in targets:
        fa: FileAnalysis | None = files.get(fk)
        if not fa:
            body.append(
                f"<div class='box warn'><b>{html.escape(fk)}</b> が見つかりませんでした。</div>"
            )
            continue

        body.append(f"<h2><code>{html.escape(fk)}</code></h2>")
        body.append("<table>")
        body.append("<tr><th>項目</th><th>内容</th></tr>")

        link: str = vscode_link(fa.path, 1)
        body.append(
            f"<tr><td>Open</td><td><a href='{html.escape(link)}'>VS Codeで開く</a></td></tr>"
        )

        up_items: list[str] = sorted(up_map.get(fk, set()))
        down_items: list[str] = sorted(down_map.get(fk, set()))
        body.append(
            "<tr><td>上流（import元）</td><td>"
            + _ul_file_links(files, up_items)
            + "</td></tr>"
        )
        body.append(
            "<tr><td>下流（import先）</td><td>"
            + _ul_file_links(files, down_items)
            + "</td></tr>"
        )

        import_lines: list[str] = []
        for imp in fa.imports:
            if imp.kind == "import":
                txt: str = ", ".join(imp.names)
            else:
                txt = f"from {imp.module} import " + ", ".join(imp.names)
            import_lines.append(
                f"<li>line {imp.lineno}: <code>{html.escape(txt)}</code></li>"
            )
        body.append(
            "<tr><td>import文</td><td><ul>" + "".join(import_lines) + "</ul></td></tr>"
        )

        body.append("</table>")

    return html_page("Alarm File Dependencies", "".join(body))


def _ul_file_links(
    files: dict[str, FileAnalysis], items: list[str]
) -> str:
    """ファイルリンクのリストを HTML で生成"""
    if not items:
        return "<span class='small'>なし</span>"
    out: list[str] = ["<ul>"]
    for fk in items:
        fa: FileAnalysis | None = files.get(fk)
        if fa:
            out.append(
                f"<li><a href='{html.escape(vscode_link(fa.path, 1))}'><code>{html.escape(fk)}</code></a></li>"
            )
        else:
            out.append(f"<li><code>{html.escape(fk)}</code></li>")
    out.append("</ul>")
    return "".join(out)


def render_internal_map(
    project_root: Path,
    file_analysis: FileAnalysis,
    cross_usage: dict[str, list[CallEdge]],
) -> str:
    """ファイル内の関数呼び出しエッジを HTML でレンダリング"""
    internal_edges: dict[str, list[CallEdge]] = build_internal_edges(file_analysis)
    defs: dict[str, DefInfo] = file_analysis.defs

    body: list[str] = []
    body.append(
        f"<p class='small'>PROJECT_ROOT: <code>{html.escape(str(project_root))}</code></p>"
    )
    body.append(
        "<div class='box'>"
        "<b>見方:</b> caller → callee。"
        "<span class='badge good'>internal</span> は同一ファイル内部で解決できた呼び出し、"
        "<span class='badge warn'>external hits</span> は他ファイルから参照された回数です。"
        "</div>"
    )

    body.append("<table>")
    body.append(
        "<tr><th>定義</th><th>位置</th><th>内部呼び出し先</th><th>他ファイルからの参照</th></tr>"
    )

    ordered_defs: list[DefInfo] = sorted(
        [d for d in defs.values() if d.kind in {"class", "function", "method"}],
        key=lambda d: (d.lineno, d.qualname),
    )

    for info in ordered_defs:
        link: str = vscode_link(file_analysis.path, info.lineno)
        target_edges: list[CallEdge] = internal_edges.get(info.qualname, [])

        if target_edges:
            callee_items: list[str] = ["<ul>"]
            for e in target_edges:
                target: str = e.resolved_to or e.callee_expr
                callee_items.append(
                    f"<li>line {e.lineno}: <code>{html.escape(target)}</code> "
                    f"<span class='small'>({html.escape(e.resolution_kind)})</span></li>"
                )
            callee_items.append("</ul>")
            callee_html: str = "".join(callee_items)
        else:
            callee_html = "<span class='small'>なし</span>"

        ext: list[CallEdge] = cross_usage.get(info.qualname, [])
        if ext:
            ext_items: list[str] = ["<ul>"]
            for e in ext[:100]:
                caller_f: str = e.caller.split(":", 1)[0] if ":" in e.caller else e.caller
                ext_items.append(
                    f"<li><code>{html.escape(caller_f)}</code> line {e.lineno}"
                    f" <span class='small'>via {html.escape(e.callee_expr)}</span></li>"
                )
            ext_items.append("</ul>")
            ext_html = "".join(ext_items)
        else:
            ext_html = "<span class='small'>なし</span>"

        body.append(
            "<tr>"
            f"<td><code>{html.escape(info.qualname)}</code><br><span class='small'>{html.escape(info.kind)}</span></td>"
            f"<td><a href='{html.escape(link)}'>line {info.lineno}</a></td>"
            f"<td>{callee_html}</td>"
            f"<td>{ext_html}</td>"
            "</tr>"
        )

    body.append("</table>")
    return html_page(f"Internal Map - {file_analysis.file_key}", "".join(body))


def render_split_hints(
    project_root: Path,
    file_analysis: FileAnalysis,
    hints: dict[str, object],
) -> str:
    """分割ヒントを HTML でレンダリング"""
    body: list[str] = []
    body.append(
        f"<p class='small'>PROJECT_ROOT: <code>{html.escape(str(project_root))}</code></p>"
    )
    body.append(
        "<div class='box'>"
        "このページは『どこでブロック分割しやすいか』を見るためのヒントです。"
        " prefix と内部結合度・外部参照数を混ぜて並べています。"
        "</div>"
    )

    public_surface: list[str] = hints["public_surface"]  # type: ignore[assignment]
    heavy_nodes: list[str] = hints["heavy_nodes"]  # type: ignore[assignment]
    buckets: dict[str, list[str]] = hints["buckets"]  # type: ignore[assignment]
    scores: dict[str, MethodScore] = hints["method_scores"]  # type: ignore[assignment]

    body.append("<h2>外部から触られている public surface 候補</h2>")
    if public_surface:
        body.append("<ul>")
        for q in public_surface:
            s: MethodScore = scores[q]
            info: DefInfo = file_analysis.defs[q]
            body.append(
                f"<li><a href='{html.escape(vscode_link(file_analysis.path, info.lineno))}'><code>{html.escape(q)}</code></a>"
                f" - external={s.external_hits}, internal_in={s.internal_in}, internal_out={s.internal_out}</li>"
            )
        body.append("</ul>")
    else:
        body.append("<p class='small'>外部参照は見つかりませんでした。</p>")

    body.append("<h2>結合が強そうなノード（上位20）</h2>")
    body.append(
        "<table><tr><th>定義</th><th>bucket</th><th>internal_in</th><th>internal_out</th><th>external_hits</th></tr>"
    )
    for q in heavy_nodes[:20]:
        s: MethodScore = scores[q]
        info: DefInfo = file_analysis.defs[q]
        body.append(
            "<tr>"
            f"<td><a href='{html.escape(vscode_link(file_analysis.path, info.lineno))}'><code>{html.escape(q)}</code></a></td>"
            f"<td>{html.escape(str(s.bucket))}</td>"
            f"<td>{s.internal_in}</td>"
            f"<td>{s.internal_out}</td>"
            f"<td>{s.external_hits}</td>"
            "</tr>"
        )
    body.append("</table>")

    body.append("<h2>prefix ベースのブロック候補</h2>")
    for bucket, members in buckets.items():
        body.append(
            f"<div class='box'><h3>{html.escape(bucket)} ({len(members)})</h3><ul>"
        )
        for q in members:
            info: DefInfo = file_analysis.defs[q]
            s: MethodScore = scores[q]
            body.append(
                f"<li><a href='{html.escape(vscode_link(file_analysis.path, info.lineno))}'><code>{html.escape(q)}</code></a>"
                f" <span class='small'>line {info.lineno} / in={s.internal_in} / out={s.internal_out} / ext={s.external_hits}</span></li>"
            )
        body.append("</ul></div>")

    return html_page(f"Split Hints - {file_analysis.file_key}", "".join(body))


def render_index(target_files: list[str], summary_path: Path) -> str:
    """インデックスページを HTML でレンダリング"""
    body = [
        "<div class='box'>",
        "<p>生成された解析レポートへの入口です。</p>",
        f"<p class='small'>summary json: <code>{html.escape(str(summary_path.name))}</code></p>",
        "</div>",
        "<ul>",
        "<li><a href='file_dependencies.html'>file_dependencies.html</a></li>",
    ]
    for name in target_files:
        stem = Path(name).stem
        body.append(
            f"<li><a href='{html.escape(stem)}_internal_map.html'>{html.escape(stem)}_internal_map.html</a></li>"
        )
        body.append(
            f"<li><a href='{html.escape(stem)}_split_hints.html'>{html.escape(stem)}_split_hints.html</a></li>"
        )
    body.append("</ul>")
    return html_page("Alarm Project Mapper - Index", "".join(body))


# ============================================================
# サマリー JSON
# ============================================================


def build_summary(
    files: dict[str, FileAnalysis],
    up_map: dict[str, set[str]],
    down_map: dict[str, set[str]],
    target_files: list[str],
) -> dict[str, object]:
    """サマリー JSON を構築"""
    data: dict[str, object] = {
        "files_total": len(files),
        "targets": {},
    }

    targets_data: dict[str, object] = {}
    for fk in target_files:
        fa: FileAnalysis | None = files.get(fk)
        if not fa:
            targets_data[fk] = {"missing": True}
            continue

        defs_count: Counter[str] = Counter(d.kind for d in fa.defs.values())
        unresolved: int = sum(1 for e in fa.call_edges if not e.resolved_to)
        resolved: int = len(fa.call_edges) - unresolved
        targets_data[fk] = {
            "defs_count": dict(defs_count),
            "call_edges_total": len(fa.call_edges),
            "call_edges_resolved": resolved,
            "call_edges_unresolved": unresolved,
            "upstream_files": sorted(up_map.get(fk, set())),
            "downstream_files": sorted(down_map.get(fk, set())),
        }

    data["targets"] = targets_data
    return data


# ============================================================
# project root 解決
# ============================================================


def detect_project_root(cli_value: str | None) -> Path:
    """プロジェクトのルートディレクトリを検出"""
    if cli_value:
        return Path(cli_value).resolve()

    script_dir: Path = Path(__file__).resolve().parent
    candidates: list[Path] = [
        script_dir,
        script_dir.parent,
    ]
    for c in candidates:
        if (c / "gui.py").exists() or (c / "alarm_manager_temp.py").exists():
            return c
    return script_dir


# ============================================================
# main
# ============================================================


def main() -> int:
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Alarm プロジェクト専用解析ツール")
    parser.add_argument("--project-root", default=None, help="解析対象ルート")
    parser.add_argument(
        "--targets",
        nargs="*",
        default=list(TARGET_FILES_DEFAULT),
        help="重点解析するファイル名",
    )
    args: argparse.Namespace = parser.parse_args()

    project_root: Path = detect_project_root(args.project_root)
    if not project_root.exists():
        print(f"[ERROR] project root not found: {project_root}")
        return 1

    print(f"[INFO] project_root = {project_root}")
    files: dict[str, FileAnalysis] = analyze_project(project_root, DEFAULT_EXCLUDE_DIRS)
    if not files:
        print("[ERROR] no python files found")
        return 1

    resolve_cross_file_calls(files)
    up_map: dict[str, set[str]]
    down_map: dict[str, set[str]]
    up_map, down_map = build_dependency_maps(files)

    target_files: list[str] = []
    for t in args.targets:
        match: str | None = None
        for fk in files:
            if fk == t or Path(fk).name == t:
                match = fk
                break
        if match:
            target_files.append(match)
        else:
            target_files.append(t)

    out_dir: Path = ensure_out_dir(project_root)

    # 1) file dependencies
    file_dep_html: str = render_file_dependencies(
        project_root, files, up_map, down_map, target_files
    )
    (out_dir / "file_dependencies.html").write_text(file_dep_html, encoding="utf-8")

    # 2) target internal map + split hints
    for fk in target_files:
        fa: FileAnalysis | None = files.get(fk)
        if not fa:
            continue
        cross_usage: dict[str, list[CallEdge]] = build_cross_file_usage(files, fk)
        internal_html: str = render_internal_map(project_root, fa, cross_usage)
        split_hints: dict[str, object] = build_split_hints(fa, cross_usage)
        split_html: str = render_split_hints(project_root, fa, split_hints)

        stem: str = Path(fk).stem
        (out_dir / f"{stem}_internal_map.html").write_text(
            internal_html, encoding="utf-8"
        )
        (out_dir / f"{stem}_split_hints.html").write_text(split_html, encoding="utf-8")

    # 3) summary json
    summary: dict[str, Any] = build_summary(files, up_map, down_map, target_files)
    summary_path: Path = out_dir / "analysis_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 4) index
    index_html: str = render_index(target_files, summary_path)
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    print("[OK] analysis generated")
    print(out_dir)
    for p in sorted(out_dir.glob("*")):
        print(f" - {p.name}")

    return 0


if __name__ == "__main__":
    """エントリーポイント"""
    raise SystemExit(main())
