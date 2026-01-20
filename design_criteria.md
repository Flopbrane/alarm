# next_fire_date の責務

- Internal（AlarmStateInternal）
  - date 型で保持
  - scheduler により更新される
  - 永続化対象

- Json（AlarmStateJson）
  - str ("YYYY-MM-DD") / None で保持
  - 再起動後の状態復元用

- UI 編集モデル（AlarmUI）
  - 持たせない（ユーザー入力ではない）

- UI 表示モデル（AlarmStateView 等）
  - 表示目的のみで保持してよい
  - str ("YYYY-MM-DD") / None で保持
  
## 次のアラーム表示について

- UI の「次のアラーム」「あと◯時間◯分」は
  AlarmStateInternal を直接参照しない
- alarm_manager.get_next_alarm() の計算結果を使用する
- next_fire_date は内部状態・永続化用であり、UI表示用ではない

### 総点検方針

- dataclass を起点に全ファイルを確認する
- mapper を最重要ポイントとする
- 値の生成元・通過点・消費点を明確にする
- strict free でも「目視確認」を省略しない
