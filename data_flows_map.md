## 全体構造（完成形イメージ）

---

## 🟦 データの入力から保存までの経路図（Write Path）

```
**\[ 人間 ]**
   ↓  （曖昧・壊れやすい・日本語）
**CUI / GUI / Dialog
   ↓  （入力情報の取り込み・吸収）
★ AlarmUI / AlarmStateUI**
   （str中心・None許容・UI都合）
   *↓
ui\_normalizer.py
   **（入力補正・省略補完・表記ゆれ吸収）***

   ↓
*ui\_validate.py
**（型の妥当性検証・str → 基本型）**
   ↓
InternalUIMapper.py
   <b>（UI → Internal 変換）</b>*
   ↓
**★ AlarmInternal / AlarmStateInternal**
   （唯一の真実・実行基準データ）
   ↓
***alarm\_manager.py***<i>
   （業務ロジック・状態遷移・スケジューリング）
   ↓  （保存用データへ変換）
InternalJsonMapper.py
</i>   ↓
**★ AlarmJson / AlarmStateJson**
   （JSON永続化専用・ISO8601）
   ↓
*alarm\_storage.py
   （ファイルI/Oのみ）*
   ↓
**★ JSONファイル**
```

---

## 🟩 データの読み取りから表示までの経路図（Read Path）

```
**★ JSONファイル**
   ↓  （読み込み）
*alarm\_storage.py
   ↓
alarm\_dict\_transfer\_reader.py
   （dict構造の吸収・順序/欠損耐性）*
   ↓
**★ AlarmJson / AlarmStateJson**
   （保存形式データ）
   ↓
*JsonToInternalMapper.py
   （Json → Internal 変換）*
   ↓
**★ AlarmInternal / AlarmStateInternal**
   （実行基準・真実のデータ）
   ↓
***alarm\_manager.py
   （状態評価・次回鳴動計算・UI用抽出）***
   ↓
*InternalUIMapper.py
   （Internal → UI 変換）*
   ↓
**★ AlarmUI / AlarmStateUI**
   （表示用・文字列中心）
   ↓
**CUI / GUI / Dialog
   ↓
\[ 人間 ]**
```

---

## 🔑 設計上の重要原則（再確認）

* **Internal は唯一の真実**
* **UI / JSON は「都合の世界」**
* **Manager は変換しない（判断のみ）**
* **Mapper は責務を越境しない**
* **Storage は I/O だけ**

---

## 🧭 この図の使いどころ

* **設計レビュー時**
* **疲れて構造を見失ったとき**
* **新しい項目を追加するとき**
* **Mapper / Manager の境界で迷ったとき**
* 
**###### *👉 「今どの層を触っているか？」を確認するための地図***





