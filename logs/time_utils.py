# pylint: disable=W0611, W0107
# pyright: reportUnnecessaryIsInstance=false
# # -*- coding: utf-8 -*-
"""時間関連のユーティリティ関数"""
#########################
# Author: F.Kurokawa
# Description:
# 時間関連のユーティリティ関数
#########################
from __future__ import annotations


from datetime import datetime, timezone, date, time, timedelta
from typing import TypeAlias, Protocol, runtime_checkable, Any,Union
from zoneinfo import ZoneInfo


@runtime_checkable
class LoggerLike(Protocol):
    """Loggerのインターフェース定義（完全版）"""

    def debug(self, message: str, context: dict[str, Any] | None = None) -> None:
        """デバッグレベルのログを出力する"""
        pass

    def info(self, message: str, context: dict[str, Any] | None = None) -> None:
        """情報レベルのログを出力する"""
        pass

    def warning(self, message: str, context: dict[str, Any] | None = None) -> None:
        """警告レベルのログを出力する"""
        pass

    def error(self, message: str, context: dict[str, Any] | None = None) -> None:
        """エラーレベルのログを出力する"""
        pass


# =========================
# 型定義
# =========================
# ISO文字列専用
ISODateTimeStr: TypeAlias = str

# UNIX時間専用
UnixTime: TypeAlias = float | int

# 安全な入力型
DateLike: TypeAlias = datetime | date | ISODateTimeStr | UnixTime | None

# JSTタイムゾーン
JST = timezone(timedelta(hours=9))


# =========================
# UnixTime → UTC日時表示(core_DATA用)
# =========================
def unix_to_utc_datetime(ts: Union[UnixTime, None]) -> datetime | None:
    """UNIX時間 → UTCDateTime"""
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except Exception as e:
        print(f"Error as {e}")
        return None


# =========================
# UnixTime → UTC日時文字列表示
# =========================
def format_unix_to_utc_time(ts: UnixTime | None) -> str:
    """UNIXTIME_to_UTC"""
    dt: datetime | None = unix_to_utc_datetime(ts)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_unix_to_utc_iso(ts: UnixTime | None) -> str:
    """UNIXTIME_to_UTC"""
    dt: datetime | None = unix_to_utc_datetime(ts)
    if dt is None:
        return ""
    return dt.isoformat(timespec="seconds")


# =========================
# UTC現在時刻
# =========================
def now_utc() -> datetime:
    """現在のUTC時刻を返す（マイクロ秒は切り捨て）"""
    return datetime.now(timezone.utc).replace(microsecond=0)


# =========================
# UTC変換
# =========================
def to_utc_datetime(
    value: DateLike = None,
    *,
    logger: LoggerLike | None = None
    ) -> datetime | None:
    """値をUTCのdatetimeに変換する"""
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=JST).astimezone(timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0)

    # dateはJSTの00:00として扱う
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0), tzinfo=JST).astimezone(timezone.utc).replace(microsecond=0)

    if isinstance(value, time):
        if logger:
            logger.warning("time単体はサポートされていません")
        return None

    if isinstance(value, str):
        try:
            dt: datetime = datetime.fromisoformat(value).replace(microsecond=0)
        except ValueError:
            if logger:
                logger.warning(f"Invalid datetime string: {value}")
            return None

        if dt.tzinfo is None:
            return dt.replace(tzinfo=JST).astimezone(timezone.utc).replace(microsecond=0)

        return dt.astimezone(timezone.utc).replace(microsecond=0)

    if logger:
        logger.warning(f"Unsupported type: {type(value)}")

    return None


# =========================
# ISO（UTC）
# =========================
def to_utc_iso(value: DateLike) -> str | None:
    """値をUTCのISOフォーマット文字列に変換する"""
    dt: datetime | None = to_utc_datetime(value)
    if dt is None:
        return None
    return dt.isoformat()


# =========================
# JST変換
# =========================
def to_jst_datetime(value: DateLike) -> datetime | None:
    """値をJSTのdatetimeに変換する（表示専用）"""
    dt: datetime | None = to_utc_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(JST)


def to_jst_str(value: DateLike) -> str | None:
    """値をJSTの文字列に変換する(表示用)"""
    dt: datetime | None = to_utc_datetime(value)
    if dt is None:
        return ""
    return dt.astimezone(JST).isoformat(timespec="seconds")
