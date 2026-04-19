# -*- coding: utf-8 -*-
"""LOGに記録された値の状態を確認する"""
#########################
# Author: F.Kurokawa
# Description:
#
#########################
from __future__ import annotations

from typing import Any, TYPE_CHECKING, cast

from logs.log_types import LogDict, LogWhat, LogWhere
from logs.log_app import get_logger

if TYPE_CHECKING:
    from multi_info_logger import AppLogger


def validate_log(
    raw: dict[str, Any],
    logger: "AppLogger" = get_logger()
) -> LogDict | None:
    """Unsafe → Safe変換"""

    # time
    if not isinstance(raw.get("time"), str):
        logger.warning(f"invalid log: missing time → {raw}")
        return None

    # trace_id
    if not isinstance(raw.get("trace_id"), str):
        logger.warning(f"invalid log: missing trace_id → {raw}")
        return None

    # level
    if not isinstance(raw.get("level"), str):
        logger.warning(f"invalid log: missing level → {raw}")
        return None

    # what
    raw_what:LogWhat | None = raw.get("what")
    if not isinstance(raw_what, dict):
        logger.warning(f"invalid log: missing what → {raw}")
        return None

    message: str | None = raw_what.get("message")
    if not isinstance(message, str):
        logger.warning(f"invalid log: missing message → {raw}")
        return None

    what: LogWhat = {"message": message}

    # where（追加🔥）
    raw_where: LogWhere | None = raw.get("where")
    if isinstance(raw_where, dict):
        where: dict[str, Any] = cast(dict[str, Any], raw_where)
    else:
        where = {}

    # output（追加🔥）
    output: Any | None = raw.get("output")
    if not isinstance(output, str):
        output = "both"

    return cast(
        LogDict,
        {
        "level": raw["level"],
        "time": raw["time"],
        "trace_id": raw["trace_id"],
        "where": where,
        "what": what,
        "context": cast(dict[str, Any], raw.get("context", {})),
        "output": output,
    })
