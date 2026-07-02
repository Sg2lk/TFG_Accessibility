import logging
from pathlib import Path

from src.config import settings


class GenericPlatform:
    name = "generic"

    def __init__(self):
        self._pyautogui = None


    def get_app_data_dir(self, app_dir_name):
        path = Path.home() / f".{app_dir_name}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def enable_dpi_awareness(self):
        return None

    def ensure_single_instance(self, mutex_name=None):
        return None

    def minimize_console_window(self):
        return False

    def show_error_dialog(self, title, message):
        logging.getLogger(__name__).error("%s\n%s", title, message)
        return False


    def get_primary_screen_size(self):
        configured_size = self._configured_screen_size()

        if configured_size is not None:
            return configured_size

        try:
            size = self._get_pyautogui().size()
            width = int(size.width)
            height = int(size.height)

            if width > 0 and height > 0:
                return width, height

        except Exception:
            pass

        return 1920, 1080

    def get_cursor_position(self):
        try:
            position = self._get_pyautogui().position()
            return int(position.x), int(position.y)
        except Exception:
            width, height = self.get_primary_screen_size()
            return width // 2, height // 2

    def move_mouse(self, x, y):
        self._get_pyautogui().moveTo(
            int(round(x)),
            int(round(y)),
            duration=0,
        )


    def left_click(self):
        self._get_pyautogui().click(button="left")

    def right_click(self):
        self._get_pyautogui().click(button="right")

    def double_click(self):
        self._get_pyautogui().doubleClick(button="left")

    def left_down(self):
        self._get_pyautogui().mouseDown(button="left")

    def left_up(self):
        self._get_pyautogui().mouseUp(button="left")

    def scroll_vertical(self, amount):
        self._get_pyautogui().scroll(int(amount))

    def scroll_horizontal(self, amount):
        pyautogui = self._get_pyautogui()
        pyautogui.keyDown("shift")
        try:
            pyautogui.scroll(int(amount))
        finally:
            pyautogui.keyUp("shift")


    def press_key(self, key):
        self._get_pyautogui().press(key)

    def hotkey(self, *keys):
        self._get_pyautogui().hotkey(*keys)

    def paste_from_clipboard(self):
        self.hotkey("ctrl", "v")


    def _get_pyautogui(self):
        if self._pyautogui is None:
            import pyautogui

            pyautogui.PAUSE = 0
            self._pyautogui = pyautogui

        return self._pyautogui

    @staticmethod
    def _configured_screen_size():
        width = _positive_int_or_none(getattr(settings, "SCREEN_WIDTH", None))
        height = _positive_int_or_none(getattr(settings, "SCREEN_HEIGHT", None))

        if width and height:
            return width, height

        return None


def _positive_int_or_none(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None

    if value <= 0:
        return None

    return value