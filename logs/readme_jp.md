# Info Logger（日本語版）

Info Logger は、  
**ログ出力・分析・可視化を一体化したログシステム**です。

---

## 🎯 これは何？

一般的なロガーは「ログを出すだけ」です。

Info Logger は違います：

- ✅ 構造化ログ（JSON Lines）
- ✅ 自動分析（エラー・trace・再起動検出）
- ✅ GUI Viewer による即時確認

👉 ログは単なる出力ではなく  
👉 **「状態変化＝イベント」**として扱います

---

## ✨ 主な特徴

### 🔍 trace_id による追跡

- 処理の流れをセッション単位で追跡可能

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
