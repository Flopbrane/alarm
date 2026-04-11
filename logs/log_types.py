# -*- coding: utf-8 -*-
"""ログの種類定義"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from __future__ import annotations
from enum import Enum
from typing import TypedDict, Any
from typing import TypeAlias, NewType
# ログの種類定義
# 　Alias = 同じ型（見た目だけ変える）
# NewType = 別型（型チェック用）
# TypeAliasは、isinstance()で判定できる単純な型エイリアス
# NewTypeは、isinstance()では使用できない、型チェッカー上では区別される特殊な型定義

# 時刻はAlias
ISODateTimeStr: TypeAlias = str
# IDはNewType
TraceId = NewType("TraceId", str)
LogLevelStr = NewType("LogLevelStr", str)
LogOutputStr = NewType("LogOutputStr", str)


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


# LogRecord = イミュータブル（変更しない前提）なので TypedDict で定義
class LogRecord(TypedDict, total=False):
    """ログレコードの構造"""

    level: str  # "INFO" など（Enumは保存時にstrへ）
    time: str  # ISO8601（UTC固定）
    trace_id: str  # 必ず存在
    where: LogWhere  # 空dictでもOK（None禁止）
    what: LogWhat  # message必須をここで担保
    context: dict[str, Any]  # 空dictでOK
    output: str  # "console" | "file" | "both"
