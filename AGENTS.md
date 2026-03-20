# 🧠 Project: Creating a Multifunctional Alarm (Kurokawa Version)

## 🔰 Overview

This is a Python-based multifunctional alarm application (with future extensibility).

The system separates configuration from runtime state.

The logger retrieves warning and error information to aid in debugging.

---

## Top Priority Issue

Fixing "Silent Breaking Bugs"

---

## UI Interaction Rules

- UI must NOT directly call Manager internal methods.
- UI must NOT modify state or storage directly.

- All UI interactions MUST go through a UI Controller layer.
- UI Controller is the ONLY entry point to the Manager.

- The UI Controller is responsible for:
  - validating input
  - converting UI data
  - calling apply_alarm_mutation()

---

## 🧱 Core Architecture

- AlarmInternal = Single reliable source of information
- AlarmStateInternal = Runtime state (reconstructible, frequently changing)
- The UI layer must not hold decision logic.

---

## 🔄 Data Flow(User Input Data Flow)

- From data entry to sounding
UI → UI Mapper → Internal Model → Manager → Scheduler → Checker → Player
- From data entry to saving			↓
UI → UI Mapper → Internal Model → Manager → Internal_to_json_mapper→Storage→Save as a JSON file

---

## 📦 Module Responsibilities

### Model

- Defines data classes only
- Does not contain logic
- Getters/setters are merely auxiliary functions
- Derived programs are multi-property conditional functions

### Storage

- Read and write JSON
- Atomic saving is required

### Mapper

- Handles all type conversions here
- Datetime and str conversions must always be performed internally within the Mapper.
- Path and str conversions must always be performed internally within the mapper.

- Converting UI data to JSON data is strictly prohibited!

### Manager

- Functions as a scheduling engine (not CRUD)
- Controls the lifecycle
- Uses only data converted to AlarmInternal and AlarmStateInternal as driving data

### Scheduler

- Calculates next_fire_datetime

### Checker

- Makes the decision for should_fire()

### Player

- Executes alarms (sounds, etc.)

---

## ⚙️ Runtime Rules

- next_fire_map is a cache (not the true source)
- fingerprint_map is for duplicate detection
- Caches must NEVER be partially updated.
- Caches must ONLY be rebuilt from source of truth.
- event_queue is reserved for future optimization.
- It must NOT be used as a source of truth.

---

## Mutation Rules

- Mutation functions must NOT:
  - update cache
  - save data
  - notify UI

- Mutation functions must ONLY:
  - modify alarms and states

---

## 🚫 Anti-Patterns (Absolutely Forbidden)

- Place decision logic within the UI
- Manipulate JSON directly outside of storage
- Use state as the true source
- Handle mixed types outside of the mapper

---

## Manager Cycle (Strict Order)

1. mutation
2. normalize
3. recalc
4. rebuild cache
5. save
6. notify

---

## 🧪 Development Rules

- Always maintain alarm_id
- Do not break existing state structures
- Prioritize safe, small changes over large-scale rewrites
- alarm.id == state.id
- Trace.id != alarm.id
- Trace.id != state.id

---

## 🧠 When changing code

- Explain the reason rather than the method
- Show the scope of impact
- Avoid rewriting unrelated modules

---

## 🎯 Recommended style

- Clear separation of responsibilities
- Minimize side effects
- Deterministic behavior

---

# 🧠 プロジェクト：多機能アラームの作成（黒川バージョン）

---

## 🔰 概要

これは、Pythonベースの多機能アラームアプリケーションです（将来的な拡張性も考慮されています）。

システムは、設定と実行時状態を分離しています。

ロガーは、デバッグを支援するために警告情報とエラー情報を取得します。

---

## 🧱 コアアーキテクチャ

- AlarmInternal = 信頼できる唯一の情報源
- AlarmStateInternal = 実行時状態（再構築可能、頻繁に変更される）
- UIレイヤーは、意思決定ロジックを保持してはなりません。

---

## UI連携ルール

- UIはManagerの内部関数を直接呼び出してはならない
- UIはstateやstorageを直接操作してはならない

- UIからの操作は必ずUIコントローラーを介すること
- UIコントローラーのみがManagerへの唯一の入口とする

- UIコントローラーの責務：
  - 入力の検証
  - データ変換
  - apply_alarm_mutation()の呼び出し

---

## 🔄 データフロー（ユーザー入力データフロー）
- データ入力からアラーム鳴動まで
UI → UIマッパー → 内部モデル → マネージャー → スケジューラー → チェッカー → プレーヤー
- データ入力から保存まで 　　　　　　↓
UI → UIマッパー → 内部モデル → マネージャー → 内部toJSONマッパー → ストレージ → JSONファイルとして保存
---

## 📦 モジュールの責任

### モデル
- データクラスのみを定義します
- ロジックは含みません
- ゲッター/セッターは補助的な機能です
- 派生プログラムは、複数のプロパティを持つ条件付き関数です

### ストレージ
- JSONの読み書きを行います
- アトミックな保存が必要です

### マッパー
- すべての型変換をここで処理します
- datetimeとstrの変換は、常にマッパー内部で実行する必要があります。
- Pathとstrの変換は、常にマッパー内部で実行する必要があります。
- UIデータをJSONデータに変換することは厳禁です！

### マネージャー
- スケジューリングエンジンとして機能します（CRUDではありません）
- ライフサイクルを制御します
- 駆動データとして、AlarmInternalとAlarmStateInternalに変換されたデータのみを使用します

### スケジューラー
- next_fire_datetimeを計算します

### チェッカー
- should_fire()の判断を行います

### プレイヤー
- アラーム（音など）を実行します

---

## ⚙️ ランタイムルール

- next_fire_mapはキャッシュです（真のソースではありません）
- fingerprint_mapは重複検出用です
- キャッシュは常に再構築可能でなければなりません
---

## 🚫 アンチパターン（絶対に禁止）

- 判断ロジックをUI内に配置します
- ストレージの外部でJSONを直接操作します
- 状態を真のソースとして使用します
- マッパーの外部で混合型を処理します
---

## 🧪 開発ルール

- alarm_idを常に維持します
- 実行します既存の状態構造を破壊しない
- 大規模な書き換えよりも、安全で小規模な変更を優先する
- alarm.id == state.id
- Trace.id != alarm.id
- Trace.id != state.id
---

## 🧠 コードを変更する際

- 方法ではなく、変更の理由を説明する
- 影響範囲を示す
- 無関係なモジュールの書き換えを避ける
---

## 🎯 推奨スタイル
- 責任の明確な分離
- 副作用の最小化
- 決定論的な動作