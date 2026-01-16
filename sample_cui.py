# -*- coding: utf-8 -*-

#########################
# Author: F.Kurokawa
# Description:
#
#########################

import json
import sys
from datetime import datetime
import pygame
import time
import tkinter as tk
from tkinter import ttk, messagebox
from alarm_manager import AlarmManager 
# アラーム管理モジュールをインポート
# ------------------------------------------
# 🔹 ダミーモジュール定義（pygame用）
# ------------------------------------------
class _NotImplementedModule:
    """ダミーモジュールクラス"""

    _NOT_IMPLEMENTED_ = True

    def __init__(self, name, urgent=0):
        self.name = name
        self.urgent = urgent
        exc_type, exc_msg = sys.exc_info()[:2]
        self.info = str(exc_msg)
        self.reason = f"{exc_type.__name__}: {self.info}"
        if urgent:
            self.warn()
            
    def __getattr__(self, var):
        if not self.urgent:
            self.warn()
            self.urgent = 1
        missing_msg = f"{self.name} module not available ({self.reason})"
        raise NotImplementedError(missing_msg)
    
    def __bool__(self):
        return False
    
    def warn(self):
        msg_type = "import" if self.urgent else "use"
        message = f"{msg_type} {self.name}: {self.info}\n({self.reason})"
        try:
            import warnings

            level = 4 if self.urgent else 3
            warnings.warn(message, RuntimeWarning, level)
        except ImportError:
            print(message)
try:
    import pygame
except ImportError:
    pygame = _NotImplementedModule("pygame")  # type: ignore
def play_alarm(sound_path: str, duration: int = 10) -> None:
    """指定されたサウンドファイルを再生する"""
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(sound_path)
        pygame.mixer.music.play()
        print(f"🎵 アラーム再生中: {sound_path}（{duration}秒）")
        time.sleep(duration)
        pygame.mixer.music.stop()
        print("🛑 アラーム再生停止")
    except Exception as e:
        print(f"⚠️ 再生エラー: {e}")
# ------------------------------------------
# 🔹 アラーム監視ループ
def alarm_loop(manager: AlarmManager) -> None:
    """1分ごとにアラームをチェックして鳴動する"""
    print("⏳ アラーム監視を開始します。Ctrl+Cで停止します。")
    try:
        while True:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            print(f"現在時刻: {now}")

            due_alarms = manager.find_due_alarms()
            if due_alarms:
                for alarm in due_alarms:
                    print(f"\n🔔 アラーム鳴動！: {alarm['name']}")
                    play_alarm(alarm["sound"], alarm["duration"])
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n🛑 監視を終了しました。")
        return  # ← メニューへ戻る
# -----------------------------------------
# 🔹 イベントリスナー（変更検知用）
def on_alarm_changed():
    """AlarmManagerから呼ばれるイベントリスナー"""
    print("💾 変更が検知されました！（alarms.json が更新されました）")
# ------------------------------------------
# 🔹 メインメニュー
def start_cui():
    """CUIモードでアラームマネージャーを起動"""
    manager = AlarmManager()
    manager.add_listener(on_alarm_changed)
    manager.list_alarms()
    alarm_loop(manager)
if __name__ == "__main__":
    start_cui()
# ------------------------------------------    
# 🔹 メインメニュー
def start_gui():
    """GUIモードでアラームマネージャーを起動"""
    manager = AlarmManager()
    manager.add_listener(on_alarm_changed)
    
    root = tk.Tk()
    root.title("アラームマネージャー")
    root.geometry("400x300")
    
    # 時計表示
    time_label = ttk.Label(root, text="", font=("Helvetica", 24))
    time_label.pack(pady=20)
    
    # ボタンフレーム
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)
    
    def open_settings_window(manager: AlarmManager):
        settings = tk.Toplevel(root)
        settings.title("アラーム設定")
        settings.geometry("300x200")
        
        # アラーム設定用のコントロールを追加
        ttk.Label(settings, text="アラーム名:").pack(pady=5)
        name_entry = ttk.Entry(settings)
        name_entry.pack(pady=5)
        
        ttk.Label(settings, text="時刻:").pack(pady=5)
        time_entry = ttk.Entry(settings)
        time_entry.pack(pady=5)
        
        ttk.Button(settings, text="保存", command=lambda: save_alarm(manager, name_entry.get(), time_entry.get())).pack(pady=10)
    
    def save_alarm(manager: AlarmManager, name: str, time: str):
        # アラームの保存処理
        if name and time:
            alarm_data = json.dumps({"name": name, "time": time, "sound": "default.mp3", "duration": 10})
            manager.add_alarm(alarm_data)
            messagebox.showinfo("成功", "アラームが設定されました")
    
    # ボタン配置
    ttk.Button(button_frame, text="設定", command=lambda: open_settings_window(manager)).grid(row=0, column=0, padx=10)
    ttk.Button(button_frame, text="STOP", command=manager.stop_alarm).grid(row=0, column=1, padx=10)        
    