# -*- coding: utf-8 -*-
"""
AlarmManager Graph Analyzer
call graph + cluster suggestion
"""

from __future__ import annotations

import ast
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
import subprocess
from typing import LiteralString, DefaultDict


# ===============================
# models
# ===============================


@dataclass
class CallEdge:
    """関数呼び出しの情報"""
    caller: str
    callee: str


@dataclass
class MethodInfo:
    """関数 / メソッドの情報"""
    name: str
    lineno: int


# ===============================
# AST parser
# ===============================
MAX_NODES = 30

class MethodVisitor(ast.NodeVisitor):
    """AST ノードを訪問して関数 / メソッド情報を収集"""
    def __init__(self) -> None:
        self.current: str | None = None
        self.methods: dict[str, MethodInfo] = {}
        self.edges: list[CallEdge] = []
        self.imports: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """インポート情報を収集"""
        for name in node.names:
            self.imports.add(name.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """関数定義ノードを訪問"""
        prev: str | None = self.current
        self.current = node.name

        self.methods[node.name] = MethodInfo(
            name=node.name,
            lineno=node.lineno,
        )

        self.generic_visit(node)
        self.current = prev

    def visit_Call(self, node: ast.Call) -> None:
        """関数呼び出しノードを訪問"""

        if self.current:

            if isinstance(node.func, ast.Attribute):

                name: str = node.func.attr
                self.edges.append(CallEdge(self.current, name))

            elif isinstance(node.func, ast.Name):

                name = node.func.id
                self.edges.append(CallEdge(self.current, name))

        self.generic_visit(node)


# ===============================
# cluster logic
# ===============================
def cluster_methods(methods: dict[str, MethodInfo]) -> dict[str, list[str]]:
    """関数 / メソッドをクラスタに分類"""

    clusters: DefaultDict[str, list[str]] = defaultdict(list)

    for m in methods:

        if m.startswith("run"):
            clusters["core"].append(m)

        elif m.startswith(("load", "save")):
            clusters["storage"].append(m)

        elif m.startswith(("recalc", "update", "repair")):
            clusters["runtime"].append(m)

        elif m.startswith(("notify", "fire", "trigger")):
            clusters["notify"].append(m)

        else:
            clusters["misc"].append(m)

    return clusters


# ===============================
# graphviz
# ===============================
def build_phase_graph():
    """AlarmManager の処理フェーズのグラフを構築"""
    lines: list[str] = []
    lines.append("digraph G {")
    lines.append("rankdir=TB;")

    phases: list[str] = [
        "begin_cycle",
        "load_phase",
        "recalc_phase",
        "fire_phase",
        "save_phase",
        "notify",
        "stop_phase",
    ]

    for p in phases:
        lines.append(f'"{p}" [shape=box];')

    for i in range(len(phases) - 1):
        lines.append(f'"{phases[i]}" -> "{phases[i+1]}";')

    lines.append("}")
    return "\n".join(lines)


# ===============================
# html
# ===============================


def render_cluster_html(clusters: dict[str, list[str]]) -> str:
    """クラスタ情報を HTML にレンダリング"""
    body: list[str] = []
    body.append("<h1>AlarmManager Cluster Suggestion</h1>")

    for c, items in clusters.items():

        body.append(f"<h2>{c}</h2>")
        body.append("<ul>")

        for m in items:
            body.append(f"<li>{m}</li>")

        body.append("</ul>")

    return "\n".join(body)


# ===============================
# main
# ===============================


def main() -> None:
    """分析実行"""
    target = Path("alarm_manager_temp.py")

    tree: ast.Module = ast.parse(target.read_text(encoding="utf-8"))

    visitor = MethodVisitor()
    visitor.visit(tree)

    methods: dict[str, MethodInfo] = visitor.methods
    edges: list[CallEdge] = visitor.edges

    clusters: dict[str, list[str]] = cluster_methods(methods)

    out = Path("analysis_out")
    out.mkdir(exist_ok=True)

    dot: str = build_phase_graph()

    dot_file: Path = out / "manager_call_graph.dot"
    dot_file.write_text(dot, encoding="utf-8")

    subprocess.run(
        ["dot", "-Tsvg", str(dot_file), "-o", str(out / "manager_call_graph.svg")],
        check=True
    )

    html: str = render_cluster_html(clusters)

    (out / "manager_clusters.html").write_text(html, encoding="utf-8")

    print("analysis complete")


if __name__ == "__main__":
    main()
