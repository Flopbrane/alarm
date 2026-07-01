# -*- coding: utf-8 -*-
"""
TIMER_TICK      → 毎秒用。通知しない。
STARTUP_SYNC    → 起動時用。読み込み・保存・通知する。
CONFIG_CHANGED → 追加/編集/削除用。保存・通知する。
CUI_STARTUP    → CUI起動用。通知しない。
TEST_*         → テスト専用。
"""

#########################
# Author: F.Kurokawa
# Description:
# アラームマネージャーのサイクル制御オプションを定義するモジュール。
#########################

# cycle_options.py など

from dataclasses import dataclass

@dataclass(frozen=True)
class CycleOptions:
    """Alarm manager cycle control options."""
    load: bool = False
    fire: bool = False
    save: bool = False
    notify: bool = False
    validate: bool = False


# ===== 実働モード用定義（モジュール定数）=====

# ===== 定期監視用 =====
TIMER_TICK = CycleOptions(
    load=False,
    fire=True,
    save=False,
    notify=False,
    validate=False,
)

# ===== 起動同期用 =====
STARTUP_SYNC = CycleOptions(
    load=True,
    fire=False,
    save=True,
    notify=True,
    validate=True,
)

# ===== 設定変更用 =====
CONFIG_CHANGED = CycleOptions(
    load=False,
    fire=False,
    save=True,
    notify=True,
    validate=True,
)

# ===== CUI起動用 =====
CUI_STARTUP = CycleOptions(
    load=True,
    fire=False,
    save=False,
    notify=False,
    validate=True,
)

# ===== テスト用 =====
TEST_CONFIG_CHANGED = CycleOptions(
    load=True,
    fire=True,
    save=True,
    notify=True,
    validate=True,
)
