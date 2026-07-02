import os
from pathlib import Path

import time

from src.platforms.base import GenericPlatform


class WindowsPlatform(GenericPlatform):
    name = "windows"

    def __init__(self):
        super().__init__()
        self._win32api = None
        self._win32con = None


    def get_app_data_dir(self, app_dir_name):
        local_appdata = os.environ.get("LOCALAPPDATA")

        if local_appdata:
            path = Path(local_appdata) / app_dir_name
            path.mkdir(parents=True, exist_ok=True)
            return path

        return super().get_app_data_dir(app_dir_name)

    def enable_dpi_awareness(self):
        try:
            import ctypes

            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()

        except Exception:
            pass

    def ensure_single_instance(self, mutex_name=None):
        try:
            import ctypes
            import sys
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            create_mutex = kernel32.CreateMutexW
            create_mutex.argtypes = [
                wintypes.LPVOID,
                wintypes.BOOL,
                wintypes.LPCWSTR,
            ]
            create_mutex.restype = wintypes.HANDLE

            mutex_name = mutex_name or "Local\\TFGAccessibilitySingleInstanceMutex"
            mutex = create_mutex(None, False, mutex_name)

            if ctypes.get_last_error() == 183:
                sys.exit(0)

            return mutex

        except Exception:
            return None

    def minimize_console_window(self):
        try:
            import ctypes

            console_window = ctypes.windll.kernel32.GetConsoleWindow()
            if console_window:
                ctypes.windll.user32.ShowWindow(console_window, 6)
                return True

        except Exception:
            pass

        return False

    def show_error_dialog(self, title, message):
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                str(message),
                str(title),
                0x10,
            )
            return True

        except Exception:
            return super().show_error_dialog(title, message)


    def get_primary_screen_size(self):
        configured_size = self._configured_screen_size()

        if configured_size is not None:
            return configured_size

        try:
            win32api, _ = self._get_win32()

            width = int(win32api.GetSystemMetrics(0))
            height = int(win32api.GetSystemMetrics(1))

            if width > 0 and height > 0:
                return width, height

        except Exception:
            pass

        return super().get_primary_screen_size()

    def get_cursor_position(self):
        try:
            win32api, _ = self._get_win32()
            x, y = win32api.GetCursorPos()
            return int(x), int(y)

        except Exception:
            return super().get_cursor_position()

    def move_mouse(self, x, y):
        try:
            win32api, _ = self._get_win32()
            win32api.SetCursorPos((int(round(x)), int(round(y))))

        except Exception:
            super().move_mouse(x, y)


    def left_click(self):
        self.left_down()
        time.sleep(0.04)
        self.left_up()

    def left_down(self):
        try:
            win32api, win32con = self._get_win32()
            win32api.mouse_event(
                win32con.MOUSEEVENTF_LEFTDOWN,
                0,
                0,
                0,
                0,
            )
        except Exception:
            super().left_down()

    def left_up(self):
        try:
            win32api, win32con = self._get_win32()
            win32api.mouse_event(
                win32con.MOUSEEVENTF_LEFTUP,
                0,
                0,
                0,
                0,
            )
        except Exception:
            super().left_up()

    def right_click(self):
        try:
            win32api, win32con = self._get_win32()
            win32api.mouse_event(
                win32con.MOUSEEVENTF_RIGHTDOWN,
                0,
                0,
                0,
                0,
            )
            time.sleep(0.04)
            win32api.mouse_event(
                win32con.MOUSEEVENTF_RIGHTUP,
                0,
                0,
                0,
                0,
            )
        except Exception:
            super().right_click()

    def double_click(self):
        self.left_click()
        time.sleep(0.08)
        self.left_click()


    def _get_win32(self):
        if self._win32api is None or self._win32con is None:
            import win32api
            import win32con

            self._win32api = win32api
            self._win32con = win32con

        return self._win32api, self._win32con
