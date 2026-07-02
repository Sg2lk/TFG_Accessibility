from src.config import settings
from src.platforms.screen import get_primary_screen_size, get_cursor_position
from src.ui.qt_keyboard_overlay import QtKeyboardOverlayController


class KeyboardOverlayManager:
    def __init__(self):
        self.overlay = None
        self.visible = False
        self.protection_rect = None

    def start(self):
        self.overlay = QtKeyboardOverlayController()
        self.overlay.start()

    def stop(self):
        self.hide()
        if self.overlay:
            self.overlay.stop()
            self.overlay = None

    def restart(self):
        self.stop()
        self.start()

    def show(self):
        if not self.overlay:
            return

        self.overlay.show()
        self.visible = True
        self.protection_rect = self._get_protection_rect()

    def hide(self):
        if self.overlay:
            self.overlay.hide()

        self.visible = False
        self.protection_rect = None

    def poll_events(self, dwell=None):
        if not self.overlay:
            return

        for event in self.overlay.poll_events():
            event_type = event.get("type")

            if event_type == "visible":
                self.visible = bool(event.get("visible"))

                if not self.visible:
                    self.protection_rect = None
                    if dwell is not None:
                        dwell.reset()

            elif event_type == "geometry":
                rect = event.get("rect_physical")
                self.protection_rect = tuple(rect) if rect is not None else None

    def is_cursor_inside_protection_area(self):
        if not self.visible:
            return False

        rect = self.protection_rect or self._get_protection_rect()
        x1, y1, x2, y2 = rect
        cursor_x, cursor_y = get_cursor_position()

        return x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2

    def _get_protection_rect(self):
        screen_width, screen_height = get_primary_screen_size()

        keyboard_width = int(
            screen_width * float(getattr(settings, "KEYBOARD_WIDTH_RATIO", 0.86))
        )
        keyboard_width = min(
            keyboard_width,
            int(getattr(settings, "KEYBOARD_MAX_WIDTH", 1400)),
        )
        keyboard_width = min(keyboard_width, screen_width - 40)
        keyboard_width = max(520, keyboard_width)

        gap = int(
            screen_width * float(getattr(settings, "KEYBOARD_GAP_RATIO", 0.006))
        )
        gap = max(6, min(gap, 10))

        row_h = int(
            screen_height
            * float(getattr(settings, "KEYBOARD_KEY_HEIGHT_RATIO", 0.050))
        )
        row_h = max(42, min(row_h, 68))

        keyboard_height = row_h * 4 + gap * 3

        bottom_margin = int(
            screen_height
            * float(getattr(settings, "KEYBOARD_BOTTOM_MARGIN_RATIO", 0.025))
        )
        bottom_margin = max(16, min(bottom_margin, 36))

        start_x = (screen_width - keyboard_width) // 2
        start_y = screen_height - keyboard_height - bottom_margin

        header_h = 50
        panel_margin = int(getattr(settings, "KEYBOARD_PROTECTION_MARGIN", 18))

        x1 = max(0, start_x - panel_margin)
        y1 = max(0, start_y - header_h - panel_margin)
        x2 = min(screen_width, start_x + keyboard_width + panel_margin)
        y2 = min(screen_height, start_y + keyboard_height + panel_margin)

        return x1, y1, x2, y2
