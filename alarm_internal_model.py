# -*- coding: utf-8 -*-
"""dataclass 定義ファイル（アラーム設定・状態の内部形式）"""
#########################
# Author: F.Kurokawa
# Description:
# dataclass 定義ファイル（アラーム設定・状態の内部形式）
#########################

# alarm_internal_model.py
from __future__ import annotations

# 標準モジュール
from dataclasses import dataclass, field
from datetime import datetime, time, date as date_class
from pathlib import Path
from typing import Optional, Union

# 自作モジュール
from alarm_types import DateType, TimeType
from constants import DEFAULT_SOUND, REPEAT_INTERNAL

# ユーティリティ関数：list[int] のデフォルト値用
def _int_list() -> list[int]:
    """list[int] のデフォルト値用のユーティリティ関数"""
    return []


@dataclass
class AlarmInternal:
    """
    アラーム設定を「内部ロジック用」に保持する dataclass

    【設計方針】
    - 内部ロジック（Scheduler / Rule / Manager）は
        「すべて datetime を基準」に動作する
    - 文字列（日付・時刻）は扱わない
    ★AlarmInternal の **「外部から触っていい属性一覧」**をコメントで書く
    ★Scheduler 側では _ 付き属性を 一切触らないと決める
    id -> UUID に変更(str にする)
    """

    # =========================
    # 🔹 識別・表示系
    # =========================
    id: str = ""
    # 行識別子（必ず先頭）
    # JSON / GUI / 内部のすべてで共通の一意ID

    name: str = ""
    # 表示名（アラーム一覧・GUI表示用）
    # ロジック上の意味は持たない

    # =========================
    # 🔹 発火時刻の基準（最重要）
    # =========================
    datetime_: datetime | TimeType = None
    # 🔑 【最重要フィールド】
    # このアラームが「何時に鳴るか」を決める唯一の基準
    #
    # - date / time プロパティはすべて、この値から派生
    # - Scheduler / Rule / Manager は必ずこれを参照する
    # - 「表示用の日時」ではなく「発火時刻の設計値」

    repeat: str = list(REPEAT_INTERNAL.values())[0]
    # 繰り返しの種類（意味だけを表す）
    # "single" / "daily" / "weekly" / "monthly" / "custom"
    #
    # ※ 何週おきかは interval_weeks が担当する

    # =========================
    # 🔹 繰り返し条件（補助パラメータ）
    # =========================
    weekday: list[int] = field(default_factory=_int_list)
    # 曜日指定（0=月〜6=日）
    # weekly / custom 用
    # 空リストの場合は曜日制限なし

    week_of_month: list[int] = field(default_factory=_int_list)
    # 第n週指定（1〜5）
    # custom 用

    interval_weeks: int = 1
    # 何週おきか（1=毎週、2=隔週、3=3週おき…）
    # repeat="weekly" / "custom" で使用
    # repeat の種類とは切り離された「数値パラメータ」

    interval_days: int | None = None
    # 何日おきか（2=2日おき、3=3日おき…）
    # repeat="days_span" で使用
    # repeat 内設定日の「数値パラメータ」

    # =========================
    # 🔹 カスタム設定（補助パラメータ）
    # =========================

    base_date_: Optional[datetime] = None
    # 🔑 繰り返し計算専用の「基準日時」
    #
    # - weekly / custom / interval_weeks 用
    # - 「いつを起点に週数を数えるか」を決める
    # - 発火時刻そのものではない
    # - GUI表示用ではない
    #
    # 例：
    #   ・「2025/1/1 を基準に2週おき」
    #   ・「この日から隔週が始まる」

    custom_desc: str = ""
    # カスタム設定の説明文（GUI表示用）

    # =========================
    # 🔹 動作制御系
    # =========================
    enabled: bool = True
    # アラーム有効 / 無効フラグ

    sound: str | Path = DEFAULT_SOUND
    # 再生する音声ファイル
    # 内部では Path に正規化される

    skip_holiday: bool = False
    # 祝日スキップするか（Rule 側で使用）

    duration: int = 10
    # 再生秒数

    snooze_minutes: int = 10
    # 1回のスヌーズ時間（分）

    snooze_limit: int = 3
    # スヌーズ可能回数の上限

    end_at: datetime | None = None
    # アラームの終了日時（指定日時以降は鳴らさない）
    # None の場合は無期限に鳴る

    # ====将来的に使用するproperty====
    # timezone_mode: Literal["local", "fixed"] = "local"
    # # 海外対応のproperty
    # timezone: str = "Asia/Tokyo"
    # # 海外対応のproperty
    # =========================

    # =========================
    # 🔹 repeat helper
    # =========================
    # ----------------------------------------------------
    # __post_init__ : sound を Path に変換
    # 「初期化__init__は dataclass に任せる。
    # でも、そのあとに“仕上げ処理”をしたい」
    # ----------------------------------------------------
    def __post_init__(self) -> None:
        """strで渡された sound を Path に変換する"""
        if not self.sound:
            self.sound = DEFAULT_SOUND
        elif isinstance(self.sound, str):
            self.sound = Path(self.sound)
    # ----------------------------------------------------
    # 🔥 time（TimeType）の getter/setter
    @property
    def date(self) -> DateType:
        """dateのgetter"""
        if self.datetime_ is None or isinstance(self.datetime_, time):
            return None
        return self.datetime_.date()

    @date.setter
    def date(self, v: DateType) -> None:
        """date を差し替える（時刻は保持）"""
        if v is None:
            self.datetime_ = None
            return

        if self.datetime_ is None:
            # 時刻がない場合は 00:00 を補完
            self.datetime_ = datetime.combine(v, time(0, 0))
        elif isinstance(self.datetime_, datetime):
            self.datetime_ = datetime.combine(v, self.datetime_.time())


    @property
    def time(self) -> TimeType:
        """timeのgetter（表示用）"""
        if self.datetime_ is None:
            return None
        if isinstance(self.datetime_, datetime):
            return self.datetime_.time()
        return self.datetime_


    @time.setter
    def time(self, v: TimeType) -> None:
        """time を差し替える（日付は保持）"""
        if v is None:
            return  # UI側で None を許さないなら何もしない

        if self.datetime_ is None:
            # 日付がない場合は「今日」を補完（または base_date）
            self.datetime_ = datetime.combine(date_class.today(), v)
        elif isinstance(self.datetime_, datetime):
            self.datetime_ = datetime.combine(self.datetime_.date(), v)

    # ----------------------------------------------------
    # 🔥 base_date_（文字列 → datetime 変換対応）
    # 🔥 repeat_base_datetime(base_date_)
    # ----------------------------------------------------
    @property
    def repeat_base_datetime(self) -> datetime | None:
        """
        繰り返し計算専用の基準日時
        ・weekly / custom / interval_weeks 用
        ・None の場合は datetime_ を基準とする
        """
        if self.base_date_ is not None:
            return self.base_date_
        if isinstance(self.datetime_, datetime):
            return self.datetime_
        return None # datetime 以外（time のみなど）の場合は None を返す

    @repeat_base_datetime.setter
    def repeat_base_datetime(self, v: datetime | None) -> None:
        """基準日時を設定（Internal では datetime のみ許可）"""
        self.base_date_ = v
