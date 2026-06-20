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

# Codex 作業指示：gui.py / json_editor.py の Error 修正と安全な分割

## 現在の状況

tests フォルダ以外の import 文は、ほぼすべて新しい構成に合わせて修正済みです。

残っている主な対象は以下の2ファイルです。

* gui.py
* json_editor.py

今回の目的は、Error 修正と責務分離です。

大規模な再設計や、関係ないモジュールの書き換えは行わないでください。

---

## 最優先方針

このプロジェクトでは、Silent Breaking Bugs を最優先で防ぎます。

そのため、以下を必ず守ってください。

* UI は Manager の内部関数を直接呼ばない
* UI は state を直接変更しない
* UI は storage を直接操作しない
* UI からの操作は必ず UI Controller 層を通す
* 型変換は Mapper 層で行う
* JSON への変換や保存処理は UI に書かない
* 既存の state 構造を壊さない
* alarm.id == state.id を維持する

---

## gui.py の扱い

gui.py は、原則として GUI の表示とユーザー操作の受付だけを担当してください。  
gui.py は画面表示とイベント受付のみを担当し、状態変更・保存・変換・修復判断は Controller / Mapper / Manager / Storage / Repair 層へ委譲してください。  

gui.py に置いてよい責務：

* メイン画面の表示
* メニューバーの表示
* 現在時刻の表示
* 次のアラーム表示
* アラームまでの残り時間表示
* ボタン・メニュー・セルクリックなどの UI イベント受付
* サブウインドウの起動
* Controller から受け取った表示用データを画面に反映する処理

gui.py に置かない責務：

* AlarmStateInternal の直接変更
* Manager 内部メソッドの直接呼び出し
* JSON データの直接生成
* JSON ファイルの直接保存
* JSON ファイルの直接読み込み
* アラーム発火判定
* next_fire_datetime の計算
* キャッシュ更新
* state 修復ロジック
* 保存処理

これらは、必要に応じて UI Controller / Mapper / Manager / Storage / Repair 系モジュールに委譲してください。

---

## gui.py の分割方針

gui.py が大きすぎる場合、以下のように小さく分割してください。

例：

* gui.py

  * アプリ起動とメインウインドウ
* alarm_list_window.py

  * アラーム一覧画面
* alarm_edit_window.py

  * アラーム追加・編集用の小ウインドウ
* alarm_cell_edit_window.py

  * 一覧セルクリック時の編集用小ウインドウ
* repair_menu_window.py

  * 記録データfile修復画面を開く入口
* ui_controller.py

  * UI から Manager へ処理を渡す唯一の入口
* ui_mapper.py

  * UI 入力値と内部モデルの変換

ただし、すでに同等のファイルやクラスが存在する場合は、新規作成ではなく既存構成に合わせてください。

---

## json_editor.py の扱い

json_editor.py は、破損した記録データfileを修復するための UI として扱ってください。

ただし、json_editor.py が直接 Storage や Manager の内部構造を壊さないようにしてください。

json_editor.py に置いてよい責務：

* 破損候補データの一覧表示
* 仮修復結果の表示
* ユーザーによる修復候補の選択
* セルクリック時の小ウインドウ表示
* ユーザーが選んだ修復内容を Controller / Repair 層へ渡す

json_editor.py に置かない責務：

* state の直接変更
* alarm_id の再生成
* 既存の state 構造破壊
* JSON 保存処理の直接実行
* Manager 内部メソッドの直接呼び出し
* UI 内での複雑な修復判断

修復判断が必要な場合は、repair 系モジュールまたは controller に切り出してください。

---

## 修正時の注意

* Error 修正を優先してください
* import path の修正を優先してください
* 既存の動作を壊さないでください
* 無関係なファイルを大きく変更しないでください
* 変更理由をコメントまたは説明に残してください
* 影響範囲を明確にしてください
* 一度に大きく書き換えず、小さく安全に分割してください

---

## 作業のゴール

1. gui.py / json_editor.py の import Error を解消する
2. UI が Manager / State / Storage を直接触らない構造に近づける
3. 小ウインドウ系の処理を必要に応じて別ファイル・別クラスへ分割する
4. 既存の AlarmInternal / AlarmStateInternal の構造を壊さない
5. Silent Breaking Bugs を増やさない

---

## 禁止事項

* gui.py に判断ロジックを集約しない
* gui.py で JSON を直接編集しない
* gui.py で state を直接変更しない
* json_editor.py で Manager の内部状態を直接変更しない
* 既存の alarm_id / state_id の対応関係を壊さない
* tests 以外の無関係なファイルを大規模に書き換えない

