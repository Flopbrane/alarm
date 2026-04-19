# -*- coding: utf-8 -*-
"""ログの種類定義"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import TypedDict, Any
from typing import TypeAlias, NewType, NotRequired

# ログの種類定義
# 　Alias = 同じ型（見た目だけ変える）
# NewType = 別型（型チェック用）
# TypeAliasは、isinstance()で判定できる単純な型エイリアス
# NewTypeは、isinstance()では使用できない、型チェッカー上では区別される特殊な型定義
# Raw → LogDict → Eventの順に、安全な形になる

# 時刻はAlias
ISODateTimeStr: TypeAlias = str
# IDはNewType
TraceId = NewType("TraceId", str)
LogLevelStr = NewType("LogLevelStr", str)
LogOutputStr = NewType("LogOutputStr", str)


# ==========================================================
# 型
# ==========================================================

# ====== 処理文字定義 ======
class EventType(Enum):
    """分析で解釈されたイベント種別"""
    ERROR = "error"
    CRITICAL = "critical"
    TRACE_JUMP = "trace_jump"
    REBOOT = "reboot"
    REPEAT_ERROR = "repeat_error"


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


# ===== class TypedDict ====
class LogWhere(TypedDict):
    """Logの発生場所"""
    line: NotRequired[int]
    module: NotRequired[str]
    file: NotRequired[str]
    function: NotRequired[str]


class LogWhat(TypedDict):
    """whatのDict"""
    message: str # ← 必須
    action: NotRequired[str]
    status: NotRequired[str]
    category: NotRequired[str]


# Validate前の不安定なDict
class RawLogRecord(TypedDict, total=False):
    """validate前の不安定Dict"""
    level: str  # "INFO" など（Enumは保存時にstrへ）
    time: str  # ISO8601（UTC固定）
    trace_id: str  # 必ず存在
    where: LogWhere  # 空dictでもOK（None禁止）
    what: LogWhat  # message必須をここで担保
    context: dict[str, Any]  # 空dictでOK
    output: str  # "console" | "file" | "both"


class LogDict(TypedDict):
    """validate後の安定Dict"""
    level: str
    time: str
    trace_id: str
    where: LogWhere
    what: LogWhat
    context: dict[str, Any]
    output: str


@dataclass(slots=True)
class Event:
    """イベント分析後のデータ"""
    type: EventType | None  # 分析結果
    level: LogLevel  # 元ログレベル ←追加🔥
    time: str
    detected_at: str  # ←追加🔥
    trace_id: TraceId
    message: str
    data: dict[str, Any]
    raw: LogDict  # 元ログ保持（デバッグ最強）
