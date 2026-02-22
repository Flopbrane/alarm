# -*- coding: utf-8 -*-
# pylint: disable=invalid-name, too-many-lines, too-many-locals, too-many-branches
"""
alarm_project_visualizer.py

Alarm プロジェクト専用の可視化ツール
--------------------------------
出力:
    analysis_out/
        index.html
        manager_phase_graph.dot
        manager_phase_graph.svg
        manager_call_graph.dot
        manager_call_graph.svg
        manager_cluster_graph.dot
        manager_cluster_graph.svg
        project_import_graph.dot
        project_import_graph.svg
        analysis_summary.json

目的:
- AlarmManager の phase 構造を見やすく分離
- AlarmManager 内部の call graph を重要ノードに絞って可視化
- 分割候補クラスタごとの graph を可視化
- プロジェクト全体の import 依存を可視化

使い方:
    python alarm_project_visualizer.py --project-root D:\\PC\\Python\\alarm

Graphviz:
- PATH が通っていれば dot を自動使用
- 通っていない場合は DOT_EXE にフルパスを書く
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections import defaultdict, Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Literal

# =========================================================
# 設定
# =========================================================

# Graphviz の PATH が通っていない場合は、ここを直接指定してください
DOT_EXE = "dot"
# 例:
# DOT_EXE = r"C:\Program Files\Graphviz\bin\dot.exe"

EXCLUDE_DIRS: set[str] = {
    ".deprecated",
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
    "analysis_out",
    "contents_class_def",
    "call_index_out",
}

MANAGER_FILE_CANDIDATES: tuple[str, ...] = (
    "alarm_manager_temp.py",
    "alarm_manager.py",
)

MANAGER_CLASS_CANDIDATES: tuple[str, ...] = ("AlarmManager",)

PHASE_METHOD_ORDER: list[str] = [
    "_begin_cycle",
    "_load_phase",
    "_recalc_phase",
    "_fire_phase",
    "_save_phase",
    "_notify_listeners",
    "_check_invalid_states",
    "_stop_phase",
]

HTML_STYLE = """
body {
    font-family: "Segoe UI", sans-serif;
    line-height: 1.45;
    margin: 20px;
}
h1, h2, h3 { margin-top: 1.2em; }
code {
    background: #f4f4f4;
    padding: 0.08em 0.3em;
    border-radius: 4px;
}
.box {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 12px;
    margin: 12px 0;
}
.small {
    color: #666;
    font-size: 0.92em;
}
ul { margin-top: 0.4em; }
"""

CLUSTER_COLORS: dict[str, str] = {
    "public_api": "lightskyblue",
    "cycle_control": "lightcyan",
    "phase_core": "lightgoldenrod1",
    "runtime": "moccasin",
    "storage": "palegreen",
    "fire_notify": "lightpink",
    "config_state": "lavender",
    "runtime_index": "khaki1",
    "helper_misc": "lightgray",
}

EDGE_COLORS: dict[str, str] = {
    "public_api": "deepskyblue4",
    "cycle_control": "cadetblue4",
    "phase_core": "goldenrod4",
    "runtime": "darkorange3",
    "storage": "forestgreen",
    "fire_notify": "firebrick3",
    "config_state": "mediumpurple4",
    "runtime_index": "gold4",
    "helper_misc": "gray35",
}

# =========================================================
# dataclass
# =========================================================


@dataclass
class CallEdge:
    """呼び出しエッジ"""

    caller: str
    callee: str
    lineno: int
    raw_expr: str = ""


@dataclass
class MethodInfo:
    """メソッド情報"""

    name: str
    lineno: int
    end_lineno: int
    cluster: str = ""
    decorators: list[str] = field(default_factory=lambda: [])


@dataclass
class ManagerAnalysis:
    """AlarmManager 解析結果"""

    file_path: Path
    class_name: str
    methods: dict[str, MethodInfo] = field(default_factory=lambda: {})
    edges: list[CallEdge] = field(default_factory=lambda: [])


@dataclass
class ImportEdge:
    """ファイル import 依存"""

    src_file: str
    dst_file: str


# =========================================================
# 共通ユーティリティ
# =========================================================


def safe_read_text(path: Path) -> str:
    """テキストファイルを安全に読み込む。UTF-8 で失敗したら CP932 で再試行"""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp932", errors="replace")


def rel_key(project_root: Path, path: Path) -> str:
    """プロジェクトルートからの相対パスを、モジュール名風に変換して返す"""
    return str(path.resolve().relative_to(project_root.resolve())).replace("\\", "/")


def module_name_from_file_key(file_key: str) -> str:
    """ファイルキーからモジュール名を生成"""
    p: Path = Path(file_key).with_suffix("")
    parts: list[str] = list(p.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def is_excluded(path: Path) -> bool:
    """指定されたパスが除外対象かどうかを判定"""
    parts: set[str] = {p.lower() for p in path.parts}
    return any(x.lower() in parts for x in EXCLUDE_DIRS)


def write_text(path: Path, text: str) -> None:
    """テキストファイルを書き込む"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_dot(dot_path: Path, svg_path: Path) -> None:
    """dot コマンドを実行して SVG を生成"""
    subprocess.run(
        [DOT_EXE, "-Tsvg", str(dot_path), "-o", str(svg_path)],
        check=True,
    )


def html_page(title: str, body: str) -> str:
    """HTML ページを生成"""
    return (
        "<!doctype html>\n"
        '<html lang="ja">\n'
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f"<style>{HTML_STYLE}</style>\n"
        f"<body><h1>{title}</h1>{body}</body></html>"
    )


# =========================================================
# AlarmManager AST 解析
# =========================================================


class AlarmManagerVisitor(ast.NodeVisitor):
    """AlarmManager クラス内メソッドと self 呼び出しを収集"""

    def __init__(self, target_class_name: str) -> None:
        self.target_class_name: str = target_class_name
        self.in_target_class: bool = False
        self.current_method: str | None = None
        self.methods: dict[str, MethodInfo] = {}
        self.edges: list[CallEdge] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """クラス定義ノードを訪問"""
        if node.name == self.target_class_name:
            prev: bool = self.in_target_class
            self.in_target_class = True
            self.generic_visit(node)
            self.in_target_class = prev
        else:
            self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """関数定義ノードを訪問"""
        if not self.in_target_class:
            return

        self._visit_function_like(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """非同期関数定義ノードを訪問"""
        if not self.in_target_class:
            return

        self._visit_function_like(node)

    def _visit_function_like(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        """関数 / 非同期関数定義ノードを訪問"""
        prev: str | None = self.current_method
        self.current_method = node.name

        self.methods[node.name] = MethodInfo(
            name=node.name,
            lineno=node.lineno,
            end_lineno=getattr(node, "end_lineno", node.lineno),
            decorators=[self._decorator_name(d) for d in node.decorator_list],
        )

        self.generic_visit(node)
        self.current_method = prev

    def visit_Call(self, node: ast.Call) -> None:
        """関数呼び出しノードを訪問"""
        if not self.in_target_class or not self.current_method:
            self.generic_visit(node)
            return

        callee_name: str | None = self._resolve_call_name(node)
        if callee_name:
            self.edges.append(
                CallEdge(
                    caller=self.current_method,
                    callee=callee_name,
                    lineno=node.lineno,
                    raw_expr=self._safe_unparse(node.func),
                )
            )

        self.generic_visit(node)

    @staticmethod
    def _safe_unparse(node: ast.AST) -> str:
        """AST ノードを安全に文字列化"""
        try:
            return ast.unparse(node)
        except Exception:
            return "<expr>"

    @staticmethod
    def _decorator_name(node: ast.AST) -> str:
        """デコレータノードを安全に文字列化"""
        try:
            return ast.unparse(node)
        except Exception:
            return "<decorator>"

    def _resolve_call_name(self, node: ast.Call) -> str | None:
        """関数呼び出しノードから呼び出し先の名前を解決"""
        func = node.func

        # self.xxx()
        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id == "self":
                return func.attr

            # cls.xxx() も拾う
            if isinstance(func.value, ast.Name) and func.value.id == "cls":
                return func.attr

            # AlarmManager.xxx() が書かれていれば拾う
            if (
                isinstance(func.value, ast.Name)
                and func.value.id == self.target_class_name
            ):
                return func.attr

            return None

        # bare_name()
        if isinstance(func, ast.Name):
            return func.id

        return None


def find_manager_file(project_root: Path) -> Path:
    """AlarmManager ファイルをプロジェクトルートから探索"""
    for name in MANAGER_FILE_CANDIDATES:
        p: Path = project_root / name
        if p.exists():
            return p

    for p in project_root.rglob("*.py"):
        if is_excluded(p):
            continue
        if p.name in MANAGER_FILE_CANDIDATES:
            return p

    raise FileNotFoundError("AlarmManager ファイルが見つかりませんでした。")


def analyze_manager(manager_file: Path) -> ManagerAnalysis:
    """AlarmManager ファイルを解析"""
    source: str = safe_read_text(manager_file)
    tree: ast.Module = ast.parse(source, filename=str(manager_file))

    class_names_in_file: set[str] = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }

    target_class: str | None = None
    for c in MANAGER_CLASS_CANDIDATES:
        if c in class_names_in_file:
            target_class = c
            break

    if target_class is None:
        raise ValueError("AlarmManager クラスが見つかりませんでした。")

    visitor: AlarmManagerVisitor = AlarmManagerVisitor(target_class_name=target_class)
    visitor.visit(tree)

    return ManagerAnalysis(
        file_path=manager_file,
        class_name=target_class,
        methods=visitor.methods,
        edges=visitor.edges,
    )


# =========================================================
# クラスタ分類
# =========================================================


def classify_method(name: str) -> str:
    """分割推奨ブロック単位"""
    if name in {"start_cycle", "run_cycle", "_run_cycle"}:
        return "public_api"

    if name.startswith("_start_") or name.startswith("start_"):
        return "cycle_control"

    if name in {
        "_begin_cycle",
        "_load_phase",
        "_recalc_phase",
        "_fire_phase",
        "_save_phase",
        "_notify_listeners",
        "_check_invalid_states",
        "_stop_phase",
    }:
        return "phase_core"

    if name.startswith(("recalc", "_recalc", "update", "_update", "repair", "_repair")):
        return "runtime"

    if name.startswith(("load", "_load", "save", "_save", "serialize", "deserialize")):
        return "storage"

    if name.startswith(
        (
            "fire",
            "_fire",
            "trigger",
            "_trigger",
            "notify",
            "_notify",
            "mark",
            "_mark",
            "snooze",
            "_snooze",
        )
    ):
        return "fire_notify"

    if "config" in name or "state" in name or "normalize" in name or "validate" in name:
        return "config_state"

    if "map" in name or "fingerprint" in name or "index" in name or "queue" in name:
        return "runtime_index"

    return "helper_misc"


def attach_cluster_labels(analysis: ManagerAnalysis) -> None:
    """解析結果の MethodInfo に cluster ラベルを付与"""
    for info in analysis.methods.values():
        info.cluster = classify_method(info.name)


# =========================================================
# call graph 補助
# =========================================================


def filter_internal_edges(analysis: ManagerAnalysis) -> list[CallEdge]:
    """内部呼び出しエッジのみをフィルタリング"""
    method_names: set[str] = set(analysis.methods)
    return [
        e
        for e in analysis.edges
        if e.caller in method_names and e.callee in method_names
    ]


def build_adjacency(edges: Iterable[CallEdge]) -> dict[str, set[str]]:
    """呼び出しエッジから隣接リストを構築"""
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adj[e.caller].add(e.callee)
    return adj


def choose_call_graph_nodes(analysis: ManagerAnalysis, max_nodes: int = 40) -> set[str]:
    """
    重要ノードを絞る。
    1) アンカーから到達できるもの
    2) 接続数が高いもの
    """
    edges: list[CallEdge] = filter_internal_edges(analysis)
    adj: dict[str, set[str]] = build_adjacency(edges)

    anchors: list[str] = [
        n
        for n in (
            "start_cycle",
            "_start_startup_cycle",
            "_start_running_cycle",
            "_start_config_changed_cycle",
            "_run_cycle",
            "run_cycle",
            "_begin_cycle",
            "_load_phase",
            "_recalc_phase",
            "_fire_phase",
            "_save_phase",
            "_notify_listeners",
            "_stop_phase",
        )
        if n in analysis.methods
    ]

    selected: set[str] = set()
    q: deque[str] = deque(anchors)

    while q and len(selected) < max_nodes:
        cur: str = q.popleft()
        if cur in selected:
            continue
        selected.add(cur)
        for nxt in sorted(adj.get(cur, set())):
            if nxt not in selected:
                q.append(nxt)

    if len(selected) < max_nodes:
        degree: Counter[str] = Counter[str]()
        for e in edges:
            degree[e.caller] += 1
            degree[e.callee] += 1

        for name, _cnt in degree.most_common():
            if len(selected) >= max_nodes:
                break
            selected.add(name)

    return selected


# =========================================================
# Graphviz 出力: manager phase graph
# =========================================================


def build_manager_phase_dot(analysis: ManagerAnalysis) -> str:
    """Manager phase graph を Graphviz 用の DOT 形式で構築"""
    method_names: set[str] = set(analysis.methods)

    run_node: Literal['_run_cycle'] | Literal['run_cycle'] = "_run_cycle" if "_run_cycle" in method_names else "run_cycle"
    phase_order: list[str] = [m for m in PHASE_METHOD_ORDER if m in method_names]

    start_methods: list[str] = [
        m
        for m in (
            "start_cycle",
            "_start_startup_cycle",
            "_start_running_cycle",
            "_start_config_changed_cycle",
        )
        if m in method_names
    ]

    lines: list[str] = []
    lines.append("digraph G {")
    lines.append("rankdir=TB;")
    lines.append("graph [overlap=false, splines=polyline, ranksep=0.9, nodesep=0.5];")
    lines.append("node [shape=box, style=filled, fillcolor=white, fontsize=11];")
    lines.append("edge [penwidth=1.6, color=gray30];")

    # start area
    lines.append("subgraph cluster_entry {")
    lines.append('label="entry / dispatch";')
    lines.append("style=filled;")
    lines.append("fillcolor=lightskyblue1;")
    for m in start_methods:
        lines.append(f'"{m}" [shape=box, fillcolor=aliceblue];')
    lines.append("}")

    # engine area
    lines.append("subgraph cluster_engine {")
    lines.append('label="engine";')
    lines.append("style=filled;")
    lines.append("fillcolor=lightgoldenrod1;")
    if run_node in method_names:
        lines.append(f'"{run_node}" [shape=box, fillcolor=white];')
    for m in phase_order:
        lines.append(f'"{m}" [shape=box, fillcolor=white];')
    lines.append("}")

    # dispatch edges
    if "start_cycle" in method_names:
        if "_start_startup_cycle" in method_names:
            lines.append(
                '"start_cycle" -> "_start_startup_cycle" [color=deepskyblue4];'
            )
        if "_start_running_cycle" in method_names:
            lines.append(
                '"start_cycle" -> "_start_running_cycle" [color=deepskyblue4];'
            )
        if "_start_config_changed_cycle" in method_names:
            lines.append(
                '"start_cycle" -> "_start_config_changed_cycle" [color=deepskyblue4];'
            )

    for m in (
        "_start_startup_cycle",
        "_start_running_cycle",
        "_start_config_changed_cycle",
    ):
        if m in method_names and run_node in method_names:
            lines.append(f'"{m}" -> "{run_node}" [color=cadetblue4];')

    # phase sequence
    if run_node in method_names and phase_order:
        lines.append(f'"{run_node}" -> "{phase_order[0]}" [color=goldenrod4];')
        for i in range(len(phase_order) - 1):
            lines.append(
                f'"{phase_order[i]}" -> "{phase_order[i + 1]}" [color=goldenrod4];'
            )

    lines.append("}")
    return "\n".join(lines)


# =========================================================
# Graphviz 出力: manager call graph
# =========================================================
def build_manager_call_dot(analysis: ManagerAnalysis) -> str:
    """Manager call graph を Graphviz 用の DOT 形式で構築"""
    attach_cluster_labels(analysis)
    all_edges: list[CallEdge] = filter_internal_edges(analysis)
    selected: set[str] = choose_call_graph_nodes(analysis, max_nodes=42)

    lines: list[str] = []
    lines.append("digraph G {")
    lines.append("rankdir=LR;")
    lines.append("graph [overlap=false, splines=true, nodesep=0.55, ranksep=1.0];")
    lines.append("node [shape=ellipse, style=filled, fillcolor=white, fontsize=10];")
    lines.append("edge [penwidth=1.4];")

    # cluster別 subgraph
    grouped: dict[str, list[str]] = defaultdict(list)
    for name in sorted(selected, key=lambda x: analysis.methods[x].lineno):
        grouped[analysis.methods[name].cluster].append(name)

    for cluster_name, items in grouped.items():
        fill: str = CLUSTER_COLORS.get(cluster_name, "white")
        lines.append(f"subgraph cluster_{cluster_name} {{")
        lines.append(f'label="{cluster_name}";')
        lines.append("style=filled;")
        lines.append(f"fillcolor={fill};")
        for m in items:
            shape: Literal['box'] | Literal['ellipse'] = "box" if cluster_name in {"public_api", "phase_core"} else "ellipse"
            lines.append(f'"{m}" [shape={shape}, fillcolor=white];')
        lines.append("}")

    for e in all_edges:
        if e.caller not in selected or e.callee not in selected:
            continue
        cluster_name: str = analysis.methods[e.caller].cluster
        color: str = EDGE_COLORS.get(cluster_name, "black")
        lines.append(
            f'"{e.caller}" -> "{e.callee}" [color={color}, tooltip="line {e.lineno}"];'
        )

    lines.append("}")
    return "\n".join(lines)


# =========================================================
# Graphviz 出力: manager cluster graph
# =========================================================


def build_manager_cluster_dot(analysis: ManagerAnalysis) -> str:
    """Manager cluster graph を Graphviz 用の DOT 形式で構築"""
    attach_cluster_labels(analysis)
    all_edges: list[CallEdge] = filter_internal_edges(analysis)

    # cluster 内部エッジのみ描く
    internal_cluster_edges: list[CallEdge] = []
    for e in all_edges:
        c1: str = analysis.methods[e.caller].cluster
        c2: str = analysis.methods[e.callee].cluster
        if c1 == c2:
            internal_cluster_edges.append(e)

    grouped: dict[str, list[str]] = defaultdict(list)
    for name, info in analysis.methods.items():
        grouped[info.cluster].append(name)

    lines: list[str] = []
    lines.append("digraph G {")
    lines.append("rankdir=LR;")
    lines.append("graph [overlap=false, splines=true, nodesep=0.5, ranksep=1.1];")
    lines.append("node [shape=ellipse, style=filled, fillcolor=white, fontsize=10];")
    lines.append("edge [penwidth=1.3];")

    for cluster_name in sorted(grouped):
        items: list[str] = sorted(grouped[cluster_name], key=lambda x: analysis.methods[x].lineno)
        fill: str = CLUSTER_COLORS.get(cluster_name, "white")
        lines.append(f"subgraph cluster_{cluster_name} {{")
        lines.append(f'label="{cluster_name}";')
        lines.append("style=filled;")
        lines.append(f"fillcolor={fill};")

        for m in items:
            shape: Literal['box'] | Literal['ellipse'] = "box" if cluster_name in {"public_api", "phase_core"} else "ellipse"
            lines.append(f'"{m}" [shape={shape}, fillcolor=white];')

        lines.append("}")

    for e in internal_cluster_edges:
        cluster_name: str = analysis.methods[e.caller].cluster
        color: str = EDGE_COLORS.get(cluster_name, "black")
        lines.append(
            f'"{e.caller}" -> "{e.callee}" [color={color}, tooltip="line {e.lineno}"];'
        )

    # cluster 間は太い点線で代表エッジだけ
    seen_cluster_links: set[tuple[str, str]] = set()
    for e in all_edges:
        c1 = analysis.methods[e.caller].cluster
        c2 = analysis.methods[e.callee].cluster
        if c1 == c2:
            continue
        key: tuple[str, str] = (c1, c2)
        if key in seen_cluster_links:
            continue
        seen_cluster_links.add(key)
        lines.append(
            f'"{e.caller}" -> "{e.callee}" [style=dashed, color=gray45, penwidth=2.0];'
        )

    lines.append("}")
    return "\n".join(lines)


# =========================================================
# project import graph
# =========================================================


class ProjectImportVisitor(ast.NodeVisitor):
    """ファイルごとの import 文収集"""

    def __init__(self) -> None:
        self.imports: list[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        """Import ノードを訪問"""
        for alias in node.names:
            self.imports.append(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """ImportFrom ノードを訪問"""
        if node.module:
            self.imports.append(node.module)
        self.generic_visit(node)


def collect_project_files(project_root: Path) -> list[Path]:
    """プロジェクト内の Python ファイルを収集"""
    files: list[Path] = []
    for p in project_root.rglob("*.py"):
        if is_excluded(p):
            continue
        files.append(p)
    return sorted(files)


def build_module_to_file_map(project_root: Path, files: list[Path]) -> dict[str, str]:
    """
    module.path -> file_key
    stem -> file_key も補助的に登録
    """
    module_map: dict[str, str] = {}

    for p in files:
        fk: str = rel_key(project_root, p)
        module: str = module_name_from_file_key(fk)
        module_map[module] = fk

        stem: str = p.stem
        module_map.setdefault(stem, fk)

    return module_map


def analyze_project_imports(project_root: Path) -> tuple[list[str], list[ImportEdge]]:
    """プロジェクト内の import 文を解析"""
    files: list[Path] = collect_project_files(project_root)
    module_map: dict[str, str] = build_module_to_file_map(project_root, files)

    file_keys: list[str] = [rel_key(project_root, p) for p in files]
    edges: list[ImportEdge] = []

    for p in files:
        fk: str = rel_key(project_root, p)
        try:
            tree: ast.Module = ast.parse(safe_read_text(p), filename=str(p))
        except SyntaxError:
            continue

        visitor = ProjectImportVisitor()
        visitor.visit(tree)

        for imported_module in visitor.imports:
            parts: list[str] = imported_module.split(".")
            matched: str | None = None

            for i in range(len(parts), 0, -1):
                candidate: str = ".".join(parts[:i])
                if candidate in module_map:
                    matched = module_map[candidate]
                    break

            if matched and matched != fk:
                edges.append(ImportEdge(src_file=fk, dst_file=matched))

    # 重複削除
    uniq: set[tuple[str, str]] = {(e.src_file, e.dst_file) for e in edges}
    edges = [ImportEdge(src, dst) for src, dst in sorted(uniq)]
    return file_keys, edges


def build_project_import_dot(project_root: Path) -> str:
    """プロジェクトの import グラフを Graphviz 用の DOT 形式で構築"""
    file_keys: list[str]
    edges: list[ImportEdge]
    file_keys, edges = analyze_project_imports(project_root)

    category_colors: dict[str, str] = {
        "gui": "lightskyblue1",
        "manager": "lightgoldenrod1",
        "storage": "palegreen",
        "model": "lavender",
        "scheduler": "moccasin",
        "player": "lightpink",
        "other": "white",
    }

    def file_category(file_key: str) -> str:
        stem: str = Path(file_key).stem.lower()
        if "gui" in stem:
            return "gui"
        if "manager" in stem:
            return "manager"
        if any(x in stem for x in ("storage", "json_mapper", "mapper")):
            return "storage"
        if any(x in stem for x in ("model", "state", "internal")):
            return "model"
        if "scheduler" in stem or "checker" in stem:
            return "scheduler"
        if "player" in stem or "notify" in stem:
            return "player"
        return "other"

    lines: list[str] = []
    lines.append("digraph G {")
    lines.append("rankdir=LR;")
    lines.append("graph [overlap=false, splines=true, nodesep=0.45, ranksep=1.0];")
    lines.append("node [shape=box, style=filled, fontsize=10];")
    lines.append("edge [color=gray35, penwidth=1.4];")

    for fk in file_keys:
        fill: str = category_colors.get(file_category(fk), "white")
        lines.append(f'"{fk}" [fillcolor={fill}];')

    for e in edges:
        lines.append(f'"{e.src_file}" -> "{e.dst_file}";')

    lines.append("}")
    return "\n".join(lines)


# =========================================================
# HTML / summary
# =========================================================


def build_summary(project_root: Path, analysis: ManagerAnalysis) -> dict[str, object]:
    """解析結果の要約を構築"""
    attach_cluster_labels(analysis)
    internal_edges: list[CallEdge] = filter_internal_edges(analysis)
    cluster_counts: Counter[str] = Counter(info.cluster for info in analysis.methods.values())

    inbound: Counter[str] = Counter[str]()
    outbound: Counter[str] = Counter[str]()
    for e in internal_edges:
        outbound[e.caller] += 1
        inbound[e.callee] += 1

    heavy: list[str] = sorted(
        analysis.methods,
        key=lambda n: (
            -(inbound[n] + outbound[n]),
            analysis.methods[n].lineno,
        ),
    )

    return {
        "project_root": str(project_root),
        "manager_file": str(analysis.file_path),
        "manager_class": analysis.class_name,
        "methods_total": len(analysis.methods),
        "internal_edges_total": len(internal_edges),
        "cluster_counts": dict(cluster_counts),
        "top_connected_methods": [
            {
                "name": name,
                "lineno": analysis.methods[name].lineno,
                "cluster": analysis.methods[name].cluster,
                "inbound": inbound[name],
                "outbound": outbound[name],
            }
            for name in heavy[:20]
        ],
    }


def build_index_html(project_root: Path, summary: dict[str, object]) -> str:
    """インデックスページの HTML を構築"""
    body: list[str] = []
    body.append("<div class='box'>")
    body.append(f"<p><b>PROJECT_ROOT:</b> <code>{project_root}</code></p>")
    body.append("<p>このページは Alarm プロジェクト可視化の入口です。</p>")
    body.append("</div>")

    body.append("<h2>生成ファイル</h2>")
    body.append("<ul>")
    body.append(
        "<li><a href='manager_phase_graph.svg'>manager_phase_graph.svg</a> … phase順の全体構造</li>"
    )
    body.append(
        "<li><a href='manager_call_graph.svg'>manager_call_graph.svg</a> … 重要メソッド中心の call graph</li>"
    )
    body.append(
        "<li><a href='manager_cluster_graph.svg'>manager_cluster_graph.svg</a> … 分割候補クラスタ単位の graph</li>"
    )
    body.append(
        "<li><a href='project_import_graph.svg'>project_import_graph.svg</a> … プロジェクト全体の import 依存</li>"
    )
    body.append(
        "<li><a href='analysis_summary.json'>analysis_summary.json</a> … 要約JSON</li>"
    )
    body.append("</ul>")

    body.append("<h2>読み方</h2>")
    body.append("<div class='box'>")
    body.append(
        "<p><b>phase graph</b> は Manager の主幹です。ここがまず正しいか確認します。</p>"
    )
    body.append(
        "<p><b>call graph</b> は重要メソッド中心に絞っています。全量表示より読みやすさ優先です。</p>"
    )
    body.append(
        "<p><b>cluster graph</b> は分割候補単位です。ファイル分割の足場に使います。</p>"
    )
    body.append(
        "<p><b>import graph</b> は gui / manager / storage / model の依存を見ます。</p>"
    )
    body.append("</div>")

    body.append("<h2>summary</h2>")
    body.append("<pre>")
    body.append(json.dumps(summary, ensure_ascii=False, indent=2))
    body.append("</pre>")

    return html_page("Alarm Project Visualizer - Index", "\n".join(body))


# =========================================================
# main
# =========================================================


def main() -> int:
    """コマンドライン引数を処理して解析を実行"""
    parser = argparse.ArgumentParser(description="Alarm Project Visualizer")
    parser.add_argument(
        "--project-root",
        default=".",
        help="解析対象プロジェクトのルート",
    )
    args: argparse.Namespace = parser.parse_args()

    project_root: Path = Path(args.project_root).resolve()
    if not project_root.exists():
        print(f"[ERROR] project root not found: {project_root}")
        return 1

    try:
        manager_file: Path = find_manager_file(project_root)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 1

    print(f"[INFO] project_root = {project_root}")
    print(f"[INFO] manager_file = {manager_file}")

    try:
        manager_analysis: ManagerAnalysis = analyze_manager(manager_file)
    except Exception as e:
        print(f"[ERROR] manager analyze failed: {e}")
        return 1

    out_dir: Path = project_root / "analysis_out"
    out_dir.mkdir(parents=True, exist_ok=True)

    # manager phase graph
    phase_dot: str = build_manager_phase_dot(manager_analysis)
    phase_dot_path: Path = out_dir / "manager_phase_graph.dot"
    phase_svg_path: Path = out_dir / "manager_phase_graph.svg"
    write_text(phase_dot_path, phase_dot)

    # manager call graph
    call_dot: str = build_manager_call_dot(manager_analysis)
    call_dot_path: Path = out_dir / "manager_call_graph.dot"
    call_svg_path: Path = out_dir / "manager_call_graph.svg"
    write_text(call_dot_path, call_dot)

    # manager cluster graph
    cluster_dot: str = build_manager_cluster_dot(manager_analysis)
    cluster_dot_path: Path = out_dir / "manager_cluster_graph.dot"
    cluster_svg_path: Path = out_dir / "manager_cluster_graph.svg"
    write_text(cluster_dot_path, cluster_dot)

    # project import graph
    import_dot: str = build_project_import_dot(project_root)
    import_dot_path: Path = out_dir / "project_import_graph.dot"
    import_svg_path: Path = out_dir / "project_import_graph.svg"
    write_text(import_dot_path, import_dot)

    # graphviz 実行
    try:
        run_dot(phase_dot_path, phase_svg_path)
        run_dot(call_dot_path, call_svg_path)
        run_dot(cluster_dot_path, cluster_svg_path)
        run_dot(import_dot_path, import_svg_path)
    except FileNotFoundError:
        print("[ERROR] Graphviz の dot が見つかりません。DOT_EXE を確認してください。")
        return 1
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] dot 実行エラー: {e}")
        return 1

    summary: dict[str, object] = build_summary(project_root, manager_analysis)
    write_text(
        out_dir / "analysis_summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2),
    )

    index_html: str = build_index_html(project_root, summary)
    write_text(out_dir / "index.html", index_html)

    print("[OK] visualizer generated")
    print(out_dir)
    for p in sorted(out_dir.iterdir()):
        print(f" - {p.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
