# Info Logger（日本語版）

Info Logger は、  
**ログ出力・分析・可視化を一体化したログシステム**です。

---

## 🎯 これは何？

一般的なロガーは **「ログを出すだけ」** です。

**Info Logger は違います**：

- ✅ 構造化ログ（JSON Lines）
- ✅ 自動分析（エラー・trace・再起動検出）
- ✅ GUI Viewer による即時確認

👉 ログは単なる出力ではなく  
👉 **「状態変化＝イベント」**として扱います

---

## ✨ 主な特徴

### 🔍 trace_id による追跡

- 処理の流れをセッション単位で追跡可能
- trace.idは起動に対して、"Windows"でのソフト起動に対して、一意のIDである。

---

### 📍 発生箇所の自動取得

- ファイル / 行 / 関数を自動記録

---

### 🧠 ログ解析機能

- ERROR / CRITICAL 検出
- trace_idの変化（TRACE_JUMP）
- システム再起動検出

---

### 🖥️ GUI Viewer

- ログを即時表示
- フィルタ（type / trace_id）
- JSON詳細表示

---

### 🕒 時刻管理

- 内部処理：UTC
- 表示：ローカル時間（JST）

---

## ⚡ クイックスタート

### ① クローン

```bash
git clone https://github.com/yourname/Info_Logger.git
cd Info_Logger
```

---

### ② 基本的な使い方

```python
from logs.log_app import get_logger

logger = get_logger()

logger.info("処理開始")
logger.warning("異常検知", context={"value": 42})
logger.error("処理失敗", status="failed")
```

---

### ③ ビューアの起動

```bash
python -m logs.log_viewer
```

👉 GUIでログを即時確認

---

## 🧱 アーキテクチャ

```text
アプリケーション
    ↓
Logger（AppLogger）
    ↓
JSON Linesログファイル
    ↓
log_searcher（解析）
    ↓
イベント（LogEvent）
    ↓
log_viewer（GUI表示）
```

---

## 🧠 設計思想

- ログは「イベント」である
- LogRecordは不変（immutable）
- trace_idは「セッション単位」
- 責務分離を徹底

|    層    | 役割 |
| -------- | ---- |
| Logger   | 記録 |
| Searcher | 解析 |
| Viewer   | 表示 |

---

## 📂 プロジェクト構成

```text
logs/
├ multi_info_logger.py   # コアロガー
├ log_storage.py         # I/O層
├ log_searcher.py        # 解析
├ log_viewer.py          # GUI
├ log_types.py
├ time_utils.py
└ env_paths.py
```

## 📚 詳細ドキュメント

- 設計書 → docs/Design.md
- 使い方 → docs/How_to_use.md

---

## 🚀 今後の展開

- DB対応（SQLite / PostgreSQL）
- リアルタイム監視
- Webダッシュボード
- 通知連携（Discord / Slack）
- AIによる異常検知
- 多言語対応（英語 / 日本語）
- タイムゾーン対応・管理の強化

---

## 📄 ライセンス

- MIT License

---

## 💬 コンセプト

### これは単なるロガーではありません

#### 👉 プログラムの挙動を理解するための診断システムです

- ログは　**「状態変化＝イベント」**として扱います。
- ログは　**「文字列」ではなく「構造化されたデータ」**です。
- ログは　**「記録」だけでなく「分析・可視化」**も行えます。
- ログは　**「セッション単位」**で追跡できます。
- ログは　**「発生箇所」を自動で記録します。**
- ログは　**「リアルタイムで確認」**できます。
- ログは　**「将来の拡張性」**を考慮して設計されています。
- ログは　**「開発者の理解を深めるためのツール」**です。
- ログは　**「プログラムの挙動を可視化するためのイベント」**です。

## ## なぜこのLoggerを作成したのか

このLoggerは、通常の運用において発生しがちな
**「静かに壊れる（Silent Failure）」問題を排除すること**を目的として設計されています。

一般的なログでは、エラーが明示的に出ない限り、問題の発見が遅れたり、原因の追跡が困難になるケースがあります。
本Loggerではその課題を解決するために、**状態や意図を明示的に記録する設計**を採用しています。

特に、以下の形式で情報を記録できるようにしています。

```python
context: dict {変数 / プロパティ : 意図した値}
```

この設計により、

- 「何をしようとしていたのか」
- 「どの値を前提としていたのか」
- 「どこでズレが発生したのか」

を、ログから直接読み取ることが可能になります。

また、記述のしやすさも重視し、開発者が自然にこの情報を残せるような構造にしています。

---

このLoggerは単なる記録ツールではなく、
**「状態の透明性」を担保し、問題を早期に検知するための設計ツール**です。

## contextの使用例

以下は、context を使用してログの情報量を高める例です。

コード例

```python
logger.info(
    "ユーザーログイン処理",
    context={
        "user_id": user_id,
        "想定状態": "認証成功",
        "実際状態": auth_result,
    }
)
```

## 出力例

```text
{
  "time": "2026-04-18T10:15:30Z",
  "type": "INFO",
  "message": "ユーザーログイン処理",
  "context": {
    "user_id": "A12345",
    "想定状態": "認証成功",
    "実際状態": "失敗"
  }
}
```

---

## 異常検知例

```python
logger.warning(
    "Unexpected state detected",
    context={
        "state": current_state,
        "expected": "READY",
        "next_action": "recovery triggered"
    }
)
```

## この設計の重要性

**単に「失敗した」という情報だけ**でなく、

- 何を意図していたのか
- 実際に何が起きたのか
- どの値がズレていたのか

を**ログから直接読み取ること**ができます。

これにより、問題の特定が高速になり、
**「静かに壊れる状態」**を見逃さない設計になります。
