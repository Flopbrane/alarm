① config\_change 専用テスト設計

🎯 目的:設定変更時に即 next\_fire が再計算されること

needs\_recalc が正しく使われていること



✅ テストケース 1：enabled 切替

・手順

alarm.enabled = True → False

start\_cycle("config\_change")

start\_cycle("loop")



・期待結果

enabled=False の alarm は

state.triggered == False

state.next\_fire\_datetime が None または future に影響しない

発火しない

needs\_recalc が cycle 内で False に戻る



✅ テストケース 2：time 変更

・手順

alarm.time を未来の時刻に変更

start\_cycle("config\_change")

・期待結果

state.needs\_recalc == False

state.next\_fire\_datetime が 新しい時刻基準で更新

旧時刻は残らない



✅ テストケース 3：repeat 変更

例

* single → weekly
* weekly → single



・期待結果

repeat 変更後のルールで next\_fire 再計算

single の場合：

未発火 → next\_fire あり

発火後 → lifecycle\_finished=True, next\_fire=None



② startup → loop → loop 連続テスト

🎯 目的：needs\_recalc が暴走しない

next\_fire が安定する

✅ テストシーケンス

mgr.start\_cycle("startup")

mgr.start\_cycle("loop")

mgr.start\_cycle("loop")



・期待結果

2回目 loop で

next\_fire\_datetime が変化しない

needs\_recalc が勝手に True にならない

alarm.log に異常なし

👉 \*\*「ループは idempotent」\*\*が保証される



③ 「startup では絶対に鳴らない」保証テスト

🎯 目的：起動時の誤発火ゼロ保証



✅ テスト条件

single アラーム

date/time が 過去

enabled=True



✅ 実行

mgr.start\_cycle("startup")

・期待結果

state.triggered == False

player.play() が呼ばれない

lifecycle\_finished は

設計どおり（必要なら True）

alarm.log に警告 or 修復ログのみ（info で OK）



🧭 明日の作業順（おすすめ）

上記 ①〜③ を テストスクリプトに追加

全部 PASS を確認

AlarmManager は一旦完成扱い



👉 cui.py に着手

on\_timer() → start\_cycle("loop")

表示責務だけに集中できる状態 👍

