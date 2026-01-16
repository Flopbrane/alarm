# -*- coding: utf-8 -*-
""" datetime ↔ strType 変換ユーティリティ"""
#########################
# Author: F.Kurokawa
# Description:
# datetime → ISO8601:日時の「表記ルール（書式）」(strType)
# 変換ユーティリティ(チェック済み)
#########################
from datetime import date, datetime, time


# ===============================
# 🔹 strType → datetimeType 変換ユーティリティ
# ===============================
def str_to_datetime(v: str | None) -> datetime | None:
    """ISO8601:str → datetime"""
    if not v:
        return None
    return datetime.fromisoformat(v.replace(" ", "T"))


def date_time_to_datetime(
    date_str: str | None,
    time_str: str | None,
    ) -> datetime:
    """ISO8601:str → datetime (date or time が None の場合、現在日時で補正)"""
    if not date_str:
        date_str = date.today().strftime("%Y-%m-%d")
    if not time_str:
        time_str = datetime.now().strftime("%H:%M")
    return datetime.fromisoformat(f"{date_str}T{time_str}")


def str_to_date(v: str | None) -> date | None:
    """ISO8601:str → date"""
    if not v:
        return None
    return date.fromisoformat(v)


def str_to_time(v: str | None) -> time | None:
    """「2000年」は意図的な選択
    1970-01-01 を避けて 2000-01-01 を使うのは、
    実務ではよく使われます。

    理由は：
    ・うるう年問題と無関係
    ・タイムゾーンの罠に引っかかりにくい
    ・誰が見ても「ダミー」と分かる
    ・テストが安定する

    1970-01-01（UNIX epoch）を避けて
    2000-01-01 を使うのは、かなり“玄人寄り”です。"""
    if not v:
        return None
    return datetime.fromisoformat(f"2000-01-01T{v}").time()


def any_to_datetime(v: str | datetime | None) -> datetime | None:
    """str|datetime|None → datetime|None (安全ラッパー)"""
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    return str_to_datetime(v)


def datetime_or_now(dt: datetime | None) -> datetime:
    """None の場合は now() を返す"""
    return dt if dt else datetime.now()


# ===============================
# 🔹 datetimeType → strType 変換ユーティリティ
# ===============================
def datetime_to_str(dt: datetime | None) -> str | None:
    """datetime → ISO8601:str"""
    return dt.isoformat() if dt else None

def datetime_to_date_time(dt: datetime) -> tuple[str, str]:
    """datetime → (date:str, time:str)"""
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")

def date_to_str(d: date | None) -> str | None:
    """date → ISO8601:str"""
    return d.isoformat() if d else None

def time_to_str(t: time | None) -> str | None:
    """time → ISO8601:str"""
    return t.isoformat() if t else None
