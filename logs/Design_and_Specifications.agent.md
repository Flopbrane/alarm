# ログシステム 設計・仕様書

## 🎯 概要

本システムは、以下の3層構造で構成される。

```
ログ生成 → ログ保存 → ログ解析 → 表示
```

---

## 🧭 アーキテクチャ

```
[System / Application]
        ↓
[AppLogger]
        ↓
[JSON Lines Log File]
        ↓
[log_searcher]
        ↓
[LogEvent]
        ↓
[log_viewer]
```

---

## 🧩 各モジュールの役割

### 🔹 log_app.py

* ロガーの取得（Singleton）
* `get_logger()` により全体で1インスタンス共有

---

### 🔹 multi_info_logger.py（AppLogger）

#### 主な責務

* ログレコード生成（_build_record）
* 出力制御（_emit）
* JSON Lines形式で保存

#### ログ構造

```json
{
  "level": "INFO",
  "time": "2026-04-08T10:00:00",
  "trace_id": "xxxx",
  "where": {...},
  "what": {...},
  "context": {...},
  "output": "both"
}
```

---

### 🔹 system_monitor.py

* システム状態の監視
* イベント発生時にloggerへ通知

例：

* clock_jump
* reboot
* cpu使用率

---

### 🔹 log_searcher.py

#### 主な責務

* ログ読み込み
* イベント抽出（解析）

#### 入力

```
list[LogRecord]
```

#### 出力

```
list[LogEvent]
```

---

### 🔹 log_viewer.py

* GUI表示（Tkinter）
* イベント一覧表示
* 詳細表示

---

## 🧠 ログ設計思想

### 🔥 1. ログは「イベント」

ログは単なる出力ではなく、状態変化の記録である。

---

### 🔥 2. LogRecordは不変

* 生成後は変更しない
* スナップショットとして扱う

---

### 🔥 3. trace_id = セッション単位

* プログラム起動ごとに一意
* 再起動検知に使用

---

### 🔥 4. 責務分離

|     層     | 役割 |
| ---------- | ---- |
|   Logger   | 記録 |
|  Searcher  | 解析 |
|   Viewer   | 表示 |

---

## 🧩 LogEvent構造

```python
class LogEvent(TypedDict):
    type: str
    message: str
    timestamp: str | None
    trace_id: str | None
    data: dict[str, Any]
```

---

## 🔍 検出イベント

|    type    |    内容        |
| ---------- | -------------- |
| TRACE_JUMP | trace_idの変化  |
| ERROR      | エラー発生      |
| CLOCK_JUMP | 時刻異常        |
| REBOOT     | 再起動          |

---

## 🚀 拡張性

* DB保存
* API送信
* 分析ダッシュボード
* リアルタイム監視

---

## 📌 今後の改善案

* ログローテーション（日付・サイズ）
* イベントレベル（severity）
* trace単位グルーピング
* GUIフィルタ機能

---

## 💬 備考

本システムは「ログ出力」ではなく
**「観測・診断システム」**として設計されている。

## 参考事項

### 各型ヒントクラス
```python
# ==========================================================
# 型
# ==========================================================
class LogOutput(Enum):
    """出力先の指定"""
    CONSOLE = "console"
    FILE = "file"
    BOTH = "both"


class LogLevel(Enum):
    """ログレベルの指定"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    REBOOT = "REBOOT"  # 特殊レベル（再起動ログ用）


class LogWhere(TypedDict, total=False):
    """ログの発生箇所情報"""
    line: int
    module: str
    file: str
    function: str


class LogWhat(TypedDict, total=False):
    """ログの内容情報"""
    message: str
    action: str
    status: str
    category: str

### LogRecord = イミュータブル（変更しない前提）なので TypedDict で定義
class LogRecord(TypedDict, total=False):
    """ログレコードの情報"""
    level: LogLevel
    time: datetime | str
    trace_id: str | None
    where: LogWhere
    what: LogWhat
    context: dict[str, Any]
    output: str
```
