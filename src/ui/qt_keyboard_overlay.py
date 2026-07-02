import multiprocessing
import queue
import sys
import time


class QtKeyboardOverlayController:
    def __init__(self):
        self.ctx = multiprocessing.get_context("spawn")
        self.command_queue = self.ctx.Queue()
        self.event_queue = self.ctx.Queue()
        self.process = None

    def start(self):
        if self.process is not None and self.process.is_alive():
            return

        self.process = self.ctx.Process(
            target=_run_qt_keyboard_process,
            args=(self.command_queue, self.event_queue),
            daemon=True,
        )
        self.process.start()

    def show(self):
        self.command_queue.put({"type": "show"})

    def hide(self):
        self.command_queue.put({"type": "hide"})

    def poll_events(self):
        events = []
        while True:
            try:
                events.append(self.event_queue.get_nowait())
            except queue.Empty:
                break
        return events

    def stop(self):
        try:
            self.command_queue.put({"type": "close"})
        except Exception:
            pass

        if self.process is not None:
            self.process.join(timeout=1.0)
            if self.process.is_alive():
                self.process.terminate()
            self.process = None


def _run_qt_keyboard_process(command_queue, event_queue):
    from PySide6.QtCore import Qt, QTimer, QRectF
    from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
    from PySide6.QtWidgets import QApplication, QWidget


    from src.config import settings
    from src.config.user_config import load_and_apply_user_config
    from src.i18n import t
    from src.platforms.screen import get_cursor_position, get_primary_screen_size
    from src.platforms.factory import get_platform

    load_and_apply_user_config(settings)

    class VirtualKeyboardWindow(QWidget):
        def __init__(self):
            super().__init__()

            self.platform = get_platform()

            self.visible = False
            self.keys = []
            self.metrics = None
            self.last_protection_rect = None

            self.hover_key_id = None
            self.hover_started_at = None
            self.dwell_progress = 0.0
            self.dwell_time = 1.20
            self.activation_cooldown = 0.50
            self.last_activation_at = 0.0

            self._setup_window()
            self._setup_screen_metrics()

            self.timer = QTimer()
            self.timer.timeout.connect(self._update_hover)
            self.timer.start(16)

            self.hide()


        def _setup_window(self):
            self.setWindowFlags(
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.Tool
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)

        def _setup_screen_metrics(self):
            qt_geometry = QApplication.primaryScreen().geometry()
            self.qt_width = qt_geometry.width()
            self.qt_height = qt_geometry.height()
            self.physical_width, self.physical_height = get_primary_screen_size()
            self.scale_x = self.qt_width / max(1, self.physical_width)
            self.scale_y = self.qt_height / max(1, self.physical_height)
            self.setGeometry(0, 0, self.qt_width, self.qt_height)

        def _cursor_qt_position(self):
            x, y = get_cursor_position()
            return int(round(x * self.scale_x)), int(round(y * self.scale_y))

        def _qt_rect_to_physical(self, x1, y1, x2, y2):
            px1 = int(round(x1 / self.scale_x))
            py1 = int(round(y1 / self.scale_y))
            px2 = int(round(x2 / self.scale_x))
            py2 = int(round(y2 / self.scale_y))
            return (
                max(0, px1),
                max(0, py1),
                min(self.physical_width, px2),
                min(self.physical_height, py2),
            )

        @staticmethod
        def _clamp(value, minimum, maximum):
            return max(minimum, min(value, maximum))


        def show_keyboard(self):
            self.visible = True
            self._reset_hover()
            self._build_layout()
            self._send_protection_rect(force=True)
            self.show()
            self.update()
            event_queue.put({"type": "visible", "visible": True})

        def hide_keyboard(self):
            self.visible = False
            self._reset_hover()
            self.last_protection_rect = None
            self.hide()
            event_queue.put({"type": "visible", "visible": False})
            event_queue.put({"type": "geometry", "rect_physical": None})


        def _keyboard_metrics(self):
            width_ratio = float(getattr(settings, "KEYBOARD_WIDTH_RATIO", 0.82))
            max_width = int(getattr(settings, "KEYBOARD_MAX_WIDTH", 1250))
            gap_ratio = float(getattr(settings, "KEYBOARD_GAP_RATIO", 0.006))
            height_ratio = float(getattr(settings, "KEYBOARD_KEY_HEIGHT_RATIO", 0.050))
            bottom_ratio = float(getattr(settings, "KEYBOARD_BOTTOM_MARGIN_RATIO", 0.025))

            keyboard_width = int(self.qt_width * width_ratio)
            keyboard_width = min(keyboard_width, max_width, self.qt_width - 40)
            keyboard_width = max(520, keyboard_width)

            gap = self._clamp(int(self.qt_width * gap_ratio), 5, 10)
            key_h = self._clamp(int(self.qt_height * height_ratio), 42, 68)
            bottom_margin = self._clamp(int(self.qt_height * bottom_ratio), 16, 36)

            rows = 4
            keyboard_h = key_h * rows + gap * (rows - 1)
            start_x = (self.qt_width - keyboard_width) // 2
            start_y = self.qt_height - keyboard_h - bottom_margin
            header_h = 42
            panel_margin = 10

            return {
                "start_x": start_x,
                "start_y": start_y,
                "width": keyboard_width,
                "height": keyboard_h,
                "gap": gap,
                "key_h": key_h,
                "header_h": header_h,
                "panel_x": start_x - panel_margin,
                "panel_y": start_y - header_h,
                "panel_w": keyboard_width + panel_margin * 2,
                "panel_h": keyboard_h + header_h + panel_margin,
            }

        def _build_layout(self):
            self.keys = []
            self.metrics = self._keyboard_metrics()

            x = self.metrics["start_x"]
            y = self.metrics["start_y"]
            width = self.metrics["width"]
            gap = self.metrics["gap"]
            key_h = self.metrics["key_h"]

            for row in ("qwertyuiop", "asdfghjklñ", "zxcvbnm.,"):
                y = self._add_letter_row(row, x, y, width, key_h, gap)

            self._add_control_row(x, y, width, key_h, gap)

        def _add_letter_row(self, chars, start_x, y, total_width, key_h, gap):
            row_width = int(total_width * (0.72 if len(chars) < 9 else 1.0))
            key_w = (row_width - gap * (len(chars) - 1)) // len(chars)
            x = start_x + (total_width - row_width) // 2

            for index, char in enumerate(chars):
                self._add_key(
                    key_id=f"char_{char}",
                    label=char,
                    key_type="char",
                    value=char,
                    x=x + index * (key_w + gap),
                    y=y,
                    w=key_w,
                    h=key_h,
                )

            return y + key_h + gap

        def _add_control_row(self, start_x, y, total_width, key_h, gap):
            controls = [
                ("space", t("keyboard_space"), "space", "", 4.0),
                ("backspace", t("keyboard_backspace"), "backspace", "", 1.6),
                ("enter", t("keyboard_enter"), "enter", "", 1.3),
                ("close", t("close"), "close", "", 1.2),
            ]
            total_weight = sum(item[4] for item in controls)
            available_width = total_width - gap * (len(controls) - 1)
            x = start_x

            for key_id, label, key_type, value, weight in controls:
                key_w = int(available_width * weight / total_weight)
                self._add_key(key_id, label, key_type, value, x, y, key_w, key_h)
                x += key_w + gap

        def _add_key(self, key_id, label, key_type, value, x, y, w, h):
            self.keys.append({
                "id": key_id,
                "label": label,
                "type": key_type,
                "value": value,
                "x": int(x),
                "y": int(y),
                "w": int(w),
                "h": int(h),
            })


        def _update_hover(self):
            if not self.visible:
                return

            self._send_protection_rect(force=False)
            cursor_x, cursor_y = self._cursor_qt_position()
            key = self._key_at(cursor_x, cursor_y)
            now = time.time()

            if key is None:
                self._reset_hover()
                self.update()
                return

            if key["id"] != self.hover_key_id:
                self.hover_key_id = key["id"]
                self.hover_started_at = now
                self.dwell_progress = 0.0
                self.update()
                return

            elapsed = now - (self.hover_started_at or now)
            self.dwell_progress = min(elapsed / self.dwell_time, 1.0)

            if self.dwell_progress >= 1.0 and now - self.last_activation_at >= self.activation_cooldown:
                self.last_activation_at = now
                self._activate_key(key)
                self.hover_started_at = now
                self.dwell_progress = 0.0

            self.update()

        def _key_at(self, x, y):
            for key in self.keys:
                if key["x"] <= x <= key["x"] + key["w"] and key["y"] <= y <= key["y"] + key["h"]:
                    return key
            return None

        def _reset_hover(self):
            self.hover_key_id = None
            self.hover_started_at = None
            self.dwell_progress = 0.0

        def _activate_key(self, key):
            key_type = key["type"]

            if key_type == "char":
                self._type_text(key["value"])
            elif key_type == "space":
                self.platform.press_key("space")
            elif key_type == "backspace":
                self.platform.press_key("backspace")
            elif key_type == "enter":
                self.platform.press_key("enter")
            elif key_type == "close":
                self.hide_keyboard()

        def _type_text(self, text):
            QApplication.clipboard().setText(text)
            time.sleep(0.02)
            self.platform.paste_from_clipboard()


        def _send_protection_rect(self, force=False):
            if self.metrics is None:
                return

            margin = int(getattr(settings, "KEYBOARD_PROTECTION_MARGIN", 18))
            x1 = self.metrics["panel_x"] - margin
            y1 = self.metrics["panel_y"] - margin
            x2 = self.metrics["panel_x"] + self.metrics["panel_w"] + margin
            y2 = self.metrics["panel_y"] + self.metrics["panel_h"] + margin
            rect = self._qt_rect_to_physical(x1, y1, x2, y2)

            if force or rect != self.last_protection_rect:
                self.last_protection_rect = rect
                event_queue.put({"type": "geometry", "rect_physical": rect})


        def paintEvent(self, event):
            if not self.visible:
                return

            painter = QPainter(self)
            self._draw_panel(painter)
            self._draw_title(painter)
            self._draw_keys(painter)

        def _draw_panel(self, painter):
            m = self.metrics
            painter.setPen(QPen(QColor(220, 220, 220), 2))
            painter.setBrush(QBrush(QColor(35, 35, 35)))
            painter.drawRect(m["panel_x"], m["panel_y"], m["panel_w"], m["panel_h"])

        def _draw_title(self, painter):
            m = self.metrics
            painter.setFont(QFont("Arial", 14, QFont.Bold))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(m["start_x"], m["panel_y"] + 8, m["width"], 26),
                Qt.AlignCenter,
                t("keyboard_title"),
            )

        def _draw_keys(self, painter):
            for key in self.keys:
                hovered = key["id"] == self.hover_key_id
                self._draw_key_background(painter, key, hovered)
                if hovered:
                    self._draw_key_progress(painter, key)
                self._draw_key_label(painter, key)

        def _draw_key_background(self, painter, key, hovered):
            fill = QColor(75, 95, 150) if hovered else QColor(55, 55, 55)
            border = QColor(0, 220, 220) if hovered else QColor(220, 220, 220)
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(border, 2))
            painter.drawRect(key["x"], key["y"], key["w"], key["h"])

        def _draw_key_progress(self, painter, key):
            progress_w = int(key["w"] * self.dwell_progress)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 220, 220))
            painter.drawRect(key["x"], key["y"] + key["h"] - 7, progress_w, 7)

        def _draw_key_label(self, painter, key):
            label = str(key["label"])
            font_size = 15 if len(label) <= 6 else 11
            painter.setFont(QFont("Arial", font_size, QFont.Bold))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(key["x"], key["y"], key["w"], key["h"] - 7),
                Qt.AlignCenter,
                label,
            )

    app = QApplication(sys.argv)
    window = VirtualKeyboardWindow()

    def poll_queue():
        while True:
            try:
                message = command_queue.get_nowait()
            except queue.Empty:
                break

            message_type = message.get("type")
            if message_type == "show":
                window.show_keyboard()
            elif message_type == "hide":
                window.hide_keyboard()
            elif message_type == "close":
                window.close()
                event_queue.put({"type": "visible", "visible": False})
                app.quit()

    timer = QTimer()
    timer.timeout.connect(poll_queue)
    timer.start(16)
    app.exec()
