# -*- coding: utf-8 -*-
"""
alarm_player.py
---------------------
pygame を利用してアラーム音の再生と停止を制御するクラス群。

AlarmPlayer      : 通常のスレッド方式で停止を管理
AlarmPlayerGUI   : Tkinter の after を使って停止を管理
"""
#########################
# Author: F.Kurokawa
# Description:
# # alarm_player.py
#########################
import threading
import tkinter as tk
from time import sleep
from typing import Any, Optional

def _get_pygame() -> Any:
    # pylint: disable=import-outside-toplevel
    import pygame
    return pygame


class AlarmPlayer:
    """スレッド方式でアラーム音を再生・停止するクラス"""

    def __init__(self) -> None:
        self._initialized = False
        self._init_failed = False
        self._stop_timer: threading.Thread | None = None


    def _ensure_init(self) -> None:
        if self._initialized or self._init_failed:
            return

        try:
            py_game: Any = _get_pygame()
            py_game.mixer.init()
            self._initialized = True

        except Exception as e:  # pylint: disable=W0718
            print(f"⚠ pygame 初期化に失敗しました: {e}")
            self._init_failed = True

    def play(self, sound: str, duration: int = 10) -> None:
        """指定された音を duration 秒だけ再生する"""
        self._ensure_init()
        if self._init_failed:
            print("⚠ pygame が初期化されていないため再生できません")
            return

        py_game: Any = _get_pygame()

        # 既存の再生を止める
        self.stop()

        try:
            py_game.mixer.music.load(sound)
        except Exception as e:  # pylint: disable=W0718
            print(f"⚠ サウンド読み込みエラー: {e}")
            return

        try:
            dur = float(duration)
        except Exception as e:  # pylint: disable=W0718
            print(f"⚠ duration 変換エラー: {e}")
            dur = 10.0

        if dur <= 0:
            py_game.mixer.music.play(loops=0)
            self._stop_timer = None
            return

        py_game.mixer.music.play(-1)

        def stop_after() -> None:
            sleep(dur)
            py_game.mixer.music.stop()

        self._stop_timer = threading.Thread(target=stop_after, daemon=True)
        self._stop_timer.start()

    def stop(self) -> None:
        """再生中の音を即時停止する"""
        if self._init_failed:
            return

        py_game: Any = _get_pygame()
        py_game.mixer.music.stop()


class AlarmPlayerGUI:
    """Tk.after を利用して停止を管理する GUI 用プレーヤー"""

    def __init__(self, root: tk.Misc) -> None:
        try:
            py_game: Any = _get_pygame()
            py_game.mixer.init()
            self._init_failed = False
        except Exception as e:  # pylint: disable=W0718
            print(f"⚠ pygame 初期化に失敗しました（SDL2 エラーなど）: {e}")
            self._init_failed = True

        self.root: tk.Misc = root
        self._after_id: Optional[str] = None

    def play(self, sound: str, duration: int = 10) -> None:
        """GUI 用の再生メソッド"""
        if self._init_failed:
            print("⚠ pygame が初期化されていないため再生できません")
            return

        py_game: Any = _get_pygame()
        self.stop()

        try:
            py_game.mixer.music.load(sound)
        except Exception as e:  # pylint: disable=W0718
            print(f"⚠ サウンド読み込みエラー: {e}")
            return

        try:
            dur = float(duration)
        except Exception as e:  # pylint: disable=W0718
            print(f"⚠ duration 変換エラー: {e}")
            dur = 10.0

        if dur <= 0:
            return

        py_game.mixer.music.play(-1)
        self._after_id = self.root.after(int(dur * 1000), py_game.mixer.music.stop)

    def stop(self) -> None:
        """停止処理"""
        if self._init_failed:
            return

        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:  # pylint: disable=W0718
                pass

        py_game: Any = _get_pygame()
        py_game.mixer.music.stop()
        self._after_id = None
