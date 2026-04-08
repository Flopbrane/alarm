# ログシステム 使い方

---

## 🎯 基本の流れ

- logger取得 → ログ出力 → ログ解析 → 表示

---

## 🟢 ① ロガー取得

```python
from log_app import get_logger

logger = get_logger()
```

---

## 🟢 ② ログ出力

### 基本

```python
logger.info("処理開始")
```

---

### 詳細付き

```python
logger.warning(
    "clock_jump_detected",
    context={"diff": 180}
)
```

---

### カテゴリ付き

```python
logger.error(
    "database_error",
    action="connect",
    status="failed",
    category="db"
)
```

---

## 🟢 ③ ログファイル

保存形式：

- ファイル構造
logs/
  └ app_YYYY-MM-DD.log

- 形式：1行 = 1JSON(JSONL)

---

## 🟢 ④ ログ解析

```python
from log_searcher import load_logs, analyze_logs
from pathlib import Path

logs = load_logs(Path("logs/app_2026-04-08.log"))
events = analyze_logs(logs)

for e in events:
    print(e)
```

---

## 🟢 ⑤ GUI表示

```bash
python log_viewer.py
```

---

## 🟢 表示内容

|    項目      |     内容     |
| ------------ | ------------ |
|     time     |      時刻    |
|     type     | イベント種別 |
|   trace_id   |  セッション  |
|   message    |     内容     |

---

## 🟢 クリック機能

- 行クリックで詳細JSON表示

---

## ⚠️ 注意点

### ❌ loggerを直接生成しない

```python
AppLogger()  # NG
```

---

### ✔ 必ずこれ

```python
get_logger()
```

---

### ❌ trace_idを自分で作らない

- trace_idは「起動に対して一意のID」と定義しているため

---

### ✔ loggerに任せる

- whereは自動取得
- trace_idも自動生成
- 各ファイルのトラップでは、必要な情報を記述・取得するだけで良い

---

## 💡 よくある使い方

### デバッグ

```python
logger.debug("変数確認", context={"value": x})
```

---

### エラー検知

```python
logger.error("処理失敗", status="failed")
```

---

### システム監視

```python
logger.info("cpu_usage", context={"cpu": 30})
```

---

## 🚀 発展

- イベントフィルタ
- trace単位分析
- グラフ化

---

## 💬 まとめ

このログシステムは

- 出力ツールではなく
- 状態監視・解析ツール

として設計されている。
