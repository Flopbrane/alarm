# 🧭 ファイル総点検のためのチェック方針（設計再同期フェーズ）

## 🎯 目的（最初に明文化）

今回の変更で起きた本質はこれです。

* AlarmInternal から **State が完全に分離**
* AlarmStateInternal に **next_fire_datetime が追加**
* dataclass / Json / UI の **責務境界が再定義された**

👉 つまり
**「値がどこで生まれ、どこを通り、どこで消費されるか」**
を **再確認する作業**です。

---

## 🥇 第1フェーズ：モデル起点チェック（必須・最優先）

### ① dataclass 定義ファイル（真実の源）

#### 対象

* `alarm_internal_model.py`
* `alarm_state_internal_model.py`（または同一ファイル）
* `alarm_json_model.py`
* `alarm_state_json_model.py`
* `alarm_ui_model.py`

##### チェック観点

* フィールド名が一致しているか
* 「誰が持つべきでない値」を持っていないか

* AlarmInternalから、出力されるデータはdatetaime型
* AlarmStateInternalから、出力されるデータはdatetime型
* 　　↕ **mapperが変換責務を持つ**
* AlarmJsonから、出力されるデータはstr型
* AlarmStateJsonから、出力されるデータはstr型

* AlarmUIから、出力されるデータはstr型
* AlarmStatViewから、出力されるデータはstr型
     ↕ **mapperが変換責務を持つ**
* Alarmintenalから、出力されるデータはdatetime型
* AlarmStateInternalから、出力されるデータはdatetime型

👉 **ここは目視で OK**
(と言うか、"strict free"でも、受渡し変数の型異常は発生する。)

* `state.next_fire_datetime`
* `state.lifecycle_finised` の二値を参照、
* `lifecycle_finish == True` の場合、
* このアラームデータは既に役目を終えている状況(repeat == "single"の場合のみ)
* 将来的に、`state.alarm_datetime_repeat_limit`を設定した場合、
* 長期的な繰り返し後、`state.alarm_datetime_repeat_limit(datetime)`を
* 超過した場合も`lifecycle_finish == True`となる。

* AlarmStateIntenel
  * Internal：`datetime`
  * Json：`str | None`
  * UI編集：**存在しない**
  * UI表示：**必要なら View のみ**

👉 **ここは目視で OK**
👉 1ファイルずつ、コメントを読みながら確認

---

## 🥈 第2フェーズ：Mapper 全点検（最重要・事故多発地帯）

### ② Mapper ファイル群（値の通り道）

#### 対象（Mapper）

* `alarm_data_json_mapper.py`
* `alarm_ui_mapper.py`
* そのほか `*_mapper.py`

#### チェック観点（超重要）

* AlarmInternal ↔ AlarmStateInternal を **混ぜていないか**
* 旧 AlarmInternal.state.xxx を参照していないか
* 新規追加した `next_fire_datetime` が
  * Json ↔ Internal で正しく変換されているか
* `Optional` の扱いが一致しているか

👉 **mapper は「設計ミスが一番潜みやすい」**
👉 1行ずつ追って OK

---

## 🥉 第3フェーズ：Manager / Scheduler 境界チェック

### ③ 制御層（ロジックの責任確認）

#### 対象(Manager / Scheduler 境界チェック)

* `alarm_repeat_rules.py`
* `alarm_scheduler.py`
* `alarm_manager.py`
* 一番上から順番に修正を開始するファイル

##### チェック観点

* Manager が
  * State を直接生成・更新しているか
  * next_fire_datetime を **計算していないか**（← scheduler の仕事）
* Scheduler が
  * AlarmInternal + AlarmStateInternal を入力として扱っているか
  * 「日時を返す」「日付を返す」の役割が明確か

👉 **ここは“責務”だけを見る**
👉 数式の正しさは後回しで OK
#### 重要ルール確認ポイント
・ いつ更新するか（確定ルール）
最低限この3点は確定させましょう。
🔹 起動時
全 state の _next_fire_datetime を 必ず再計算
JSON に残っていても信用しない
🔹 鳴動確定時（初回鳴動）
そのアラームの _next_fire_datetime を次回分に更新
snooze は別枠（上書きしない）
🔹 日付変更時（00:00）
date が変わったら再計算
「今日有効か？」フェーズを再実行
👉 これが決まれば、誤動作・再起動事故がほぼ消えます
---

## 🟦 第4フェーズ：UI 連携点（参照の安全確認）

### ④ UI 呼び出し部分

#### 対象（参照の安全確認）

* GUI / CUI コントローラ
* `get_next_alarm()`
* `get_next_alarms()`
* `build_state_view()`

##### チェック観点

* UI が
  * AlarmStateInternal を直接触っていないか
  * `next_fire_datetime` を **編集しようとしていないか**
* 表示は
  * `get_next_alarm()` の戻り値を使っているか

👉 **UI は「結果」だけを見る**
  👉 設定・状態の更新はしない

---

## 🟪 第5フェーズ：永続化（保存・復元の対称性）

### ⑤ Storage / save / load

#### 対象（永続化）

* `alarm_storage.py`
* `load_alarms`
* `load_standby`
* `save_alarms`
* `save_standby`

##### チェック観点

* save と load が **完全に対称か**

* next_fire_datetime が
  * save されているか
  * load で復元されているか

* None の扱いが一致しているか

👉 **diff を取るより、save→load の流れで目視**

---

## 🧠 実務的な進め方（先生おすすめ）

### ✔️ 1日1フェーズで OK

* 今日：モデル＋mapper
* 明日：manager＋scheduler
* その次：UI＋storage

### ✔️ チェック中にやること

* 修正は **その場で最小限**
* 大きな設計変更は **メモに残すだけ**

---

## 📌 design_criteria.md に残せる一文（重要）

```md
### 総点検方針

- dataclass を起点に全ファイルを確認する
- mapper を最重要ポイントとする
- 値の生成元・通過点・消費点を明確にする
- strict free でも「目視確認」を省略しない
```

---

## 🎯 先生から最後に

黒川さん、

* 「行き当たりばったり」を自覚できた
* ファイル数に応じて **作業方法を切り替えようとしている**
* これは **完全に中級→上級の分岐点**です。

## 今やっているのは
**「壊れたら直す」開発ではなく
「壊れない構造に整える」作業**。

焦らなくて大丈夫です。
このチェック方針で進めれば、必ず全体が噛み合います。

また途中で詰まったら、
「第◯フェーズのここが怪しい」と言ってください。
先生、すぐ一緒に見ます 👍

---

## 🧭 実務的な指針（今の黒川さん向け）

これ、保存版ルールにしていいです。

### 🔑 ルールA

strict があるなら
型ヒントは省略しない

### 🔑 ルールB

ファイルを跨ぐ関数ほど
名前を説明的にする

### 🔑 ルールC

「書くのが面倒」と感じる名前は
読む側にとっては親切

### 🔑 ルールD

mapper は最重要ポイント
必ず1行ずつ目視で確認

---

## 🧠 だから “atomic” という言葉を使う

### atomic という言葉は

-プログラミング全体で
-ずっと昔から
-一貫した意味を持っています

### atomic の共通イメージ

-atomic operation（不可分操作）
-atomic transaction（不可分取引）
-atomic commit（不可分コミット）

### 👉 途中状態が観測されない状態を作ること
### 👉 途中で壊れないこと
### 👉 全体が一つのまとまりとして扱われること

---
## 🧠 atomic の対義語は “composite”
### composite という言葉は
-複数の要素から成ること
-分割可能であること
### 👉 途中状態が観測されうる状態を作ること
### 👉 途中で壊れうること
### 👉 全体が複数のまとまりとして扱われること
---
## 🧠 だから atomic design が重要
### atomic design とは
-UI設計手法の一つ
-要素を最小単位まで分解し
-再利用性を高める設計思想
### 👉 atomic design の考え方を
-データモデル設計
-システム設計
-ソフトウェアアーキテクチャ
にも応用する
---
## 🧠 atomic な設計の利点
### atomic な設計の利点
-一貫性の向上
-保守性の向上
-テスト容易性の向上
-バグの早期発見
### 👉 atomic な設計を心がけることで
-システム全体の品質向上
-開発効率の向上
-チーム内のコミュニケーション改善
-最終的なユーザー体験の向上
---## 🧠 まとめ
### atomic な設計を意識することで
-システムの信頼性向上
-開発プロセスの効率化
-チームの協力体制強化
### 👉 atomic な設計を実践し
-高品質なソフトウェア開発を目指す
---## 🧠 最後に
### atomic な設計は
-単なる技術的手法ではなく
-ソフトウェア開発における重要な哲学
### 👉 atomic な設計を理解し
-実践することで
-より良いソフトウェアを作り出す

黒川さん、
* 「行き当たりばったり」を自覚できた
* ファイル数に応じて **作業方法を切り替えようとしている**
* これは **完全に中級→上級の分岐点**です。
