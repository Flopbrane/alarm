#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
universal_grep.py
rootフォルダ配下の *.py を再帰検索し、指定文字列（複数可）の一致箇所を集計してHTMLレポート出力する。

使い方例:
  python universal_grep.py --root "D:\\PC\\Python\\alarm" --out "D:\\PC\\Python\\alarm\\grep_report.html" --terms "id: int" "get_next_id(" "uuid.uuid4"

  # 正規表現モード（例: "id\\s*:\\s*int"）
  python universal_grep.py --root . --out ./grep_report.html --regex --terms "id\\s*:\\s*int" "get_next_id\\s*\\("

  # 文字列リストをファイルから読み込み（1行1term）
  python universal_grep.py --root . --out ./grep_report.html --terms-file ./terms.txt
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
from pathlib import Path
from typing import Iterable, List, Dict, Any, Tuple, Literal


def _iter_py_files(root_dir: Path, exclude_dirs: Iterable[str]) -> Iterable[Path]:
    exclude_set: set[str] = {d.lower() for d in exclude_dirs}
    for p in root_dir.rglob("*.py"):
        # ディレクトリ除外（途中のパス要素に含まれていたらスキップ）
        parts_lower: List[str] = [x.lower() for x in p.parts]
        if any(x in exclude_set for x in parts_lower):
            continue
        yield p


def _read_text_safely(load_file_path: Path) -> str | None:
    """
    文字化け/例外で落ちないように、複数エンコードを試す。
    読めなければ None を返す。
    """
    encodings: List[str] = ["utf-8", "utf-8-sig", "cp932", "shift_jis"]
    for enc in encodings:
        try:
            return load_file_path.read_text(encoding=enc, errors="strict")
        except Exception:
            continue
    # 最後の手段: 置換しつつ読む
    try:
        return load_file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _build_patterns(terms: List[str], use_regex: bool, ignore_case: bool) -> List[re.Pattern[str]]:
    """
    _build_patterns の Docstring
    
    :param terms: 説明
    :type terms: List[str]
    :param use_regex: 説明
    :type use_regex: bool
    :param ignore_case: 説明
    :type ignore_case: bool
    :return: 説明
    :rtype: List[Pattern[str]]
    """
    flags: re.RegexFlag = re.MULTILINE
    if ignore_case:
        flags |= re.IGNORECASE

    patterns: List[re.Pattern[str]] = []
    for t in terms:
        if use_regex:
            patterns.append(re.compile(t, flags))
        else:
            patterns.append(re.compile(re.escape(t), flags))
    return patterns


def _collect_hits(
    load_file_path: Path,
    rel_path: str,
    text: str,
    patterns: List[re.Pattern[str]],
    context_lines: int,
) -> List[Dict[str, Any]]:
    """
    ヒット情報:
      - term_index
      - line_no (1-based)
      - line_text
      - context (前後行)
      - match_spans (line内のstart,end)
    """
    lines: List[str] = text.splitlines()
    hits: List[Dict[str, Any]] = []

    # 行単位で走査（大きめファイルでも扱いやすい）
    for i, line in enumerate(lines):
        line_no: int = i + 1
        for term_index, pat in enumerate(patterns):
            for m in pat.finditer(line):
                start, end = m.span()
                ctx_from: int = max(0, i - context_lines)
                ctx_to: int = min(len(lines), i + context_lines + 1)
                context: List[str] = lines[ctx_from:ctx_to]

                hits.append(
                    {
                        "file": rel_path,
                        "line_no": line_no,
                        "line": line,
                        "term_index": term_index,
                        "span": (start, end),
                        "context_from": ctx_from + 1,  # 1-based
                        "context_lines": context,
                    }
                )
    return hits


def _make_file_link(root_dir: Path, rel_path: str, line_no: int) -> str:
    """
    VS Codeで開ける可能性が高い "file:///" リンクを作る。
    ※環境によってはクリックで開けない場合もあるので、表示パスも必ず併記する。
    """
    abs_path: Path = (root_dir / rel_path).resolve()
    # Windowsのパスを file URI に
    uri_path: str = abs_path.as_posix()
    return f"file:///{uri_path}#L{line_no}"


def _render_html(
    root_dir: Path,
    terms: List[str],
    use_regex: bool,
    ignore_case: bool,
    results: Dict[str, Any],
    save_file_path: Path,
) -> None:
    now: str = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # サマリ集計
    total_files = results["total_files"]
    scanned_files = results["scanned_files"]
    unreadable_files = results["unreadable_files"]
    total_hits = results["total_hits"]
    hits_by_term = results["hits_by_term"]  # List[int]
    file_hits = results["file_hits"]        # Dict[file, List[hits]]

    def esc(s: str) -> str:
        return html.escape(s, quote=True)

    # HTML本体（シンプル、軽量）
    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append('<html lang="ja">')
    parts.append("<head>")
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    parts.append(f"<title>universal_grep report - {esc(str(root_dir))}</title>")
    parts.append("<style>")
    parts.append("""
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Noto Sans JP", sans-serif; margin: 16px; }
    .meta { color: #444; font-size: 14px; }
    .box { border: 1px solid #ddd; border-radius: 10px; padding: 12px 14px; margin: 12px 0; }
    .terms code { background: #f6f8fa; padding: 2px 6px; border-radius: 6px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border-bottom: 1px solid #eee; padding: 8px; vertical-align: top; }
    th { text-align: left; background: #fafafa; position: sticky; top: 0; }
    .file { font-weight: 700; }
    .hitline { white-space: pre-wrap; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Noto Sans Mono", monospace; font-size: 13px; }
    .ctx { margin-top: 6px; padding: 8px; border-radius: 8px; background: #fbfbfb; border: 1px dashed #e5e5e5; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; background: #eef; font-size: 12px; }
    .warn { background: #ffecec; }
    .small { font-size: 12px; color: #666; }
    a { text-decoration: none; }
    a:hover { text-decoration: underline; }
    """)
    parts.append("</style>")
    parts.append("</head>")
    parts.append("<body>")

    parts.append(f"<h1>universal_grep report</h1>")
    parts.append(f'<div class="meta">生成: {esc(now)} / root: <code>{esc(str(root_dir))}</code></div>')

    parts.append('<div class="box">')
    parts.append("<h2>検索条件</h2>")
    parts.append('<div class="terms">')
    parts.append(f"<div>mode: <span class='badge'>{'regex' if use_regex else 'literal'}</span> "
                 f"case: <span class='badge'>{'ignore' if ignore_case else 'sensitive'}</span></div>")
    parts.append("<div>terms:</div><ul>")
    for t in terms:
        parts.append(f"<li><code>{esc(t)}</code></li>")
    parts.append("</ul></div>")
    parts.append("</div>")

    parts.append('<div class="box">')
    parts.append("<h2>サマリ</h2>")
    parts.append("<ul>")
    parts.append(f"<li>対象 *.py ファイル数（検出）: {total_files}</li>")
    parts.append(f"<li>読み取り成功: {scanned_files}</li>")
    parts.append(f"<li>読み取り失敗: {unreadable_files}</li>")
    parts.append(f"<li>総ヒット数: {total_hits}</li>")
    parts.append("</ul>")
    parts.append("<h3>term別ヒット</h3>")
    parts.append("<ul>")
    for t, c in zip(terms, hits_by_term):
        parts.append(f"<li><code>{esc(t)}</code> : {c}</li>")
    parts.append("</ul>")
    parts.append("</div>")

    # ファイル別詳細
    parts.append('<div class="box">')
    parts.append("<h2>詳細（ファイル別）</h2>")
    if not file_hits:
        parts.append("<p>ヒットはありませんでした。</p>")
    else:
        parts.append("<table>")
        parts.append("<thead><tr><th>File</th><th>Hits</th></tr></thead><tbody>")
        for rel_path in sorted(file_hits.keys()):
            hits = file_hits[rel_path]
            parts.append("<tr>")
            parts.append(f"<td class='file'><code>{esc(rel_path)}</code><div class='small'>{esc(str((root_dir/rel_path).resolve()))}</div></td>")
            parts.append("<td>")
            for h in hits:
                term_index: int = h["term_index"]
                term: str = terms[term_index]
                link: str = _make_file_link(root_dir, rel_path, h["line_no"])
                parts.append("<div style='margin-bottom:10px;'>")
                parts.append(f"<div><span class='badge'>{esc(term)}</span> "
                             f" line {h['line_no']} : "
                             f"<a href='{esc(link)}'>open</a></div>")
                parts.append(f"<div class='hitline'>{esc(h['line'])}</div>")

                # context
                ctx_lines = h["context_lines"]
                ctx_from = h["context_from"]
                parts.append("<div class='ctx'>")
                for j, ctx in enumerate(ctx_lines):
                    ln = ctx_from + j
                    marker: Literal['👉'] | Literal['  '] = "👉" if ln == h["line_no"] else "  "
                    parts.append(f"<div class='hitline'>{esc(f'{marker} {ln:5d}: {ctx}')}</div>")
                parts.append("</div>")
                parts.append("</div>")
            parts.append("</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")
    parts.append("</div>")

    # unreadable list
    if results["unreadable_list"]:
        parts.append('<div class="box warn">')
        parts.append("<h2>読み取り失敗ファイル</h2>")
        parts.append("<ul>")
        for p in results["unreadable_list"]:
            parts.append(f"<li><code>{esc(p)}</code></li>")
        parts.append("</ul></div>")

    parts.append("</body></html>")

    save_file_path.parent.mkdir(parents=True, exist_ok=True)
    save_file_path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    """
    main の Docstring
    :return: 説明
    :rtype: int
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="検索対象のrootフォルダ")
    parser.add_argument("--out", required=True, help="出力HTMLパス")
    parser.add_argument("--terms", nargs="*", default=[], help="検索語（複数可）")
    parser.add_argument("--terms-file", default=None, help="検索語ファイル（1行1語）")
    parser.add_argument("--regex", action="store_true", help="terms を正規表現として扱う")
    parser.add_argument("--ignore-case", action="store_true", help="大文字小文字を無視")
    parser.add_argument("--context", type=int, default=2, help="前後コンテキスト行数（default:2）")
    parser.add_argument("--exclude-dirs", nargs="*", default=[".git", ".venv", "venv", "__pycache__", "dist", "build"],
                        help="除外ディレクトリ名（部分一致ではなくパス要素一致）")
    args: argparse.Namespace = parser.parse_args()

    root_dir: Path = Path(args.root).expanduser().resolve()
    save_file_path: Path = Path(args.out).expanduser().resolve()

    terms: List[str] = list(args.terms)
    if args.terms_file:
        tf: Path = Path(args.terms_file).expanduser()
        if tf.exists():
            raw: List[str] = tf.read_text(encoding="utf-8", errors="replace").splitlines()
            terms.extend([x.strip() for x in raw if x.strip() and not x.strip().startswith("#")])

    # terms未指定は危険なので停止（事故防止）
    if not terms:
        print("[ERROR] terms が空です。--terms または --terms-file を指定してください。")
        return 2

    patterns: List[re.Pattern[str]] = _build_patterns(terms, use_regex=args.regex, ignore_case=args.ignore_case)

    total_files = 0
    scanned_files = 0
    unreadable_files = 0
    unreadable_list: List[str] = []

    file_hits: Dict[str, List[Dict[str, Any]]] = {}
    hits_by_term: List[int] = [0] * len(terms)

    for load_file_path in _iter_py_files(root_dir, args.exclude_dirs):
        total_files += 1
        rel_path: str = str(load_file_path.relative_to(root_dir)).replace("\\", "/")
        text: str | None = _read_text_safely(load_file_path)
        if text is None:
            unreadable_files += 1
            unreadable_list.append(rel_path)
            continue

        scanned_files += 1
        hits: List[Dict[str, Any]] = _collect_hits(load_file_path, rel_path, text, patterns, context_lines=args.context)
        if hits:
            file_hits.setdefault(rel_path, []).extend(hits)
            for h in hits:
                hits_by_term[h["term_index"]] += 1

    total_hits = sum(hits_by_term)

    results: Dict[str, int | List[str] | List[int] | Dict[str, List[Dict[str, Any]]]] = {
        "total_files": total_files,
        "scanned_files": scanned_files,
        "unreadable_files": unreadable_files,
        "unreadable_list": unreadable_list,
        "total_hits": total_hits,
        "hits_by_term": hits_by_term,
        "file_hits": file_hits,
    }

    _render_html(
        root_dir=root_dir,
        terms=terms,
        use_regex=args.regex,
        ignore_case=args.ignore_case,
        results=results,
        save_file_path=save_file_path,
    )

    print(f"[OK] HTML report saved: {save_file_path}")
    print(f"     total_files={total_files}, scanned={scanned_files}, unreadable={unreadable_files}, hits={total_hits}")
    return 0


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        sys.argv.extend(
            [
                "--root",
                "D:\\PC\\Python\\alarm",
                "--out",
                "D:\\PC\\Python\\alarm\\grep_report.html",
                "--terms",
                "uuid",
            ]
        )
    raise SystemExit(main())
