# -*- coding: utf-8 -*-
"""Manager cycle control options module.
Defines CycleOptions dataclass and predefined control modes
for alarm manager cycles.
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
    validate: bool = True


# ===== 実働モード用定義（モジュール定数）=====

# =====manager.main_loop()用=====
RUNNING = CycleOptions(
    load=False,
    fire=True,
    save=True,
    notify=True,
    validate=True,
)
# =====manager.startup_sync()用=====
STARTUP = CycleOptions(
    load=True,
    fire=False,
    save=True,
    notify=False,
    validate=True,
)
# =====manager.on_alarm_config_changed()用=====
CONFIG_CHANGED = CycleOptions(
    load=False,
    fire=True,
    save=False,
    notify=True,
    validate=True,
)
# =========test_config_changed===================================
TEST_CONFIG_CHANGED = CycleOptions(
    load=False,
    fire=True,
    save=False,  # ★ テストでは必ず False
    notify=True,
    validate=True,
)
