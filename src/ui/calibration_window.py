import sys

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QBrush, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from src.config import settings
from src.config.user_config import save_user_config
from src.i18n import t


class _CalibrationWindow(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.frame_pixmap = None

        self.setWindowTitle(controller.window_name)
        self.setFocusPolicy(Qt.StrongFocus)

    def update_frame(self, frame):
        if frame is None:
            return

        height, width, channels = frame.shape
        bytes_per_line = channels * width

        image = QImage(
            frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_BGR888,
        ).copy()

        self.frame_pixmap = QPixmap.fromImage(image).scaled(
            self.controller.window_width,
            self.controller.window_height,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation,
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        if self.frame_pixmap is not None:
            painter.drawPixmap(0, 0, self.frame_pixmap)
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0))

        self._draw_calibration_ui(painter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            position = event.position()
            self.controller.handle_mouse_click(int(position.x()), int(position.y()))
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.controller.pending_action = "calibrate"
        elif event.key() == Qt.Key_Escape:
            self.controller.pending_action = "exit"
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self.controller.closing_by_code:
            self.controller.pending_action = "exit"
        event.accept()

    def _draw_calibration_ui(self, painter):
        width = self.controller.window_width
        height = self.controller.window_height
        center_x = width // 2
        center_y = height // 2

        self._draw_text(
            painter,
            t("calibration_title"),
            30,
            45,
            font_size=24,
            bold=True,
            color=self._bgr(255, 255, 255),
        )

        status_color = self._bgr(0, 180, 0) if self.controller.face_detected else self._bgr(0, 0, 220)
        face_text = (
            t("calibration_face_detected")
            if self.controller.face_detected
            else t("calibration_face_missing")
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(status_color))
        painter.drawEllipse(QPointF(40, 82), 8, 8)

        self._draw_text(
            painter,
            face_text,
            60,
            90,
            font_size=15,
            bold=True,
            color=self._bgr(255, 255, 255),
        )

        if self.controller.status_message:
            self._draw_text(
                painter,
                str(self.controller.status_message),
                30,
                height - 28,
                font_size=14,
                bold=False,
                color=self._bgr(255, 255, 255),
            )

        guide_w = int(width * 0.34)
        guide_h = int(height * 0.56)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self._bgr(255, 255, 255), 2))
        painter.drawEllipse(
            center_x - guide_w // 2,
            center_y - guide_h // 2,
            guide_w,
            guide_h,
        )

        painter.setPen(QPen(self._bgr(255, 255, 255), 1))
        painter.drawLine(center_x - 24, center_y, center_x + 24, center_y)
        painter.drawLine(center_x, center_y - 24, center_x, center_y + 24)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self._bgr(255, 255, 255)))
        painter.drawEllipse(QPointF(center_x, center_y), 4, 4)

        self._draw_simple_help(painter, width, height)

        if self.controller.zoom_controls:
            self._draw_zoom_controls(
                painter,
                self.controller.camera.get_digital_zoom(),
                self.controller.zoom_controls,
            )

        if self.controller.buttons:
            self._draw_buttons(painter, self.controller.buttons)

    def _draw_simple_help(self, painter, width, height):
        x = 30
        y = 118
        panel_w = min(390, width - 60)
        panel_h = 180

        painter.setPen(QPen(self._bgr(210, 210, 210), 1))
        painter.setBrush(QBrush(self._bgr(35, 35, 35)))
        painter.drawRect(x, y, panel_w, panel_h)

        lines = [
            t("calibration_how_title"),
            t("calibration_step_1"),
            t("calibration_step_2"),
            t("calibration_step_3"),
            t("calibration_step_4"),
        ]

        current_y = y + 28
        for index, line in enumerate(lines):
            self._draw_text(
                painter,
                line,
                x + 14,
                current_y,
                font_size=14 if index == 0 else 12,
                bold=(index == 0),
                color=self._bgr(255, 255, 255),
            )
            current_y += 32 if index == 0 else 27

        self._draw_text(
            painter,
            t("calibration_shortcuts"),
            x + 14,
            y + panel_h - 18,
            font_size=11,
            bold=False,
            color=self._bgr(220, 220, 220),
        )

    def _draw_buttons(self, painter, buttons):
        labels = {
            "settings": t("settings"),
            "calibrate": t("calibrate"),
            "exit": t("exit"),
        }

        for name, rect in buttons.items():
            x1, y1, x2, y2 = rect
            fill = self._bgr(70, 70, 70)
            border = self._bgr(220, 220, 220)

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(border, 2))
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

            label = labels.get(name, name)
            self._draw_centered_text(
                painter,
                label,
                QRectF(x1, y1, x2 - x1, y2 - y1),
                font_size=13,
                bold=True,
                color=self._bgr(255, 255, 255),
            )

    def _draw_zoom_controls(self, painter, zoom_value, controls):
        x1, y1, x2, y2 = controls["bounds"]
        minus_rect = controls.get("minus_button")
        plus_rect = controls.get("plus_button")

        painter.setBrush(QBrush(self._bgr(35, 35, 35)))
        painter.setPen(QPen(self._bgr(210, 210, 210), 1))
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        if minus_rect:
            self._draw_small_zoom_button(painter, minus_rect, t("zoom_minus"))
        if plus_rect:
            self._draw_small_zoom_button(painter, plus_rect, t("zoom_plus"))

        label = f"x{zoom_value:.1f}".replace(".0", "")
        text_x1 = minus_rect[2] if minus_rect else x1
        text_x2 = plus_rect[0] if plus_rect else x2
        self._draw_centered_text(
            painter,
            label,
            QRectF(text_x1, y1, text_x2 - text_x1, y2 - y1),
            font_size=11,
            bold=False,
            color=self._bgr(255, 255, 255),
        )

    def _draw_small_zoom_button(self, painter, rect, label):
        x1, y1, x2, y2 = rect
        painter.setBrush(QBrush(self._bgr(70, 70, 70)))
        painter.setPen(QPen(self._bgr(220, 220, 220), 1))
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

        self._draw_centered_text(
            painter,
            label,
            QRectF(x1, y1, x2 - x1, y2 - y1),
            font_size=16,
            bold=True,
            color=self._bgr(255, 255, 255),
        )

    def _draw_text(self, painter, text, x, baseline_y, font_size=12, bold=False, color=None):
        font = QFont("Arial", font_size)
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(color or self._bgr(255, 255, 255))
        painter.drawText(x, baseline_y, text)

    def _draw_centered_text(self, painter, text, rect, font_size=12, bold=False, color=None):
        font = QFont("Arial", font_size)
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(color or self._bgr(255, 255, 255))
        painter.drawText(rect, Qt.AlignCenter, text)

    @staticmethod
    def _bgr(blue, green, red):
        return QColor(red, green, blue)


class CalibrationWindowController:


    def __init__(self, camera, user_config):
        self.camera = camera
        self.user_config = user_config

        self.window_name = t("calibration_window_title")
        self.window_width = 720
        self.window_height = 480

        self.buttons = {}
        self.zoom_controls = {}
        self.pending_action = None

        self.status_message = t("calibration_status_default")
        self.face_detected = False

        self.zoom_min = 1.0
        self.zoom_max = 2.5
        self._reload_zoom_config()

        self.qt_app = None
        self.window = None
        self.closing_by_code = False

    def set_user_config(self, user_config):
        self.user_config = user_config

    def refresh_after_config_change(self, user_config=None):
        if user_config is not None:
            self.user_config = user_config

        self.window_name = t("calibration_window_title")
        self._reload_zoom_config()

        if self.window is not None:
            self.window.setWindowTitle(self.window_name)

    def _reload_zoom_config(self):
        self.zoom_min = float(getattr(settings, "CAMERA_DIGITAL_ZOOM_MIN", 1.0))
        self.zoom_max = float(getattr(settings, "CAMERA_DIGITAL_ZOOM_MAX", 2.5))

    def setup_window(self, screen_width, screen_height):
        self._ensure_qt_app()

        self.window_width = max(720, int(screen_width * 0.75))
        self.window_height = max(480, int(screen_height * 0.75))

        if self.window is None:
            self.window = _CalibrationWindow(self)

        self.window.setWindowTitle(self.window_name)
        self.window.setFixedSize(self.window_width, self.window_height)


        self.window.show()
        self._center_window_on_qt_screen()

        self.window.raise_()
        self.window.activateWindow()
        self.window.setFocus()
        self.process_events()

    def _center_window_on_qt_screen(self):
        if self.window is None:
            return

        screen = self.window.screen() or QApplication.primaryScreen()
        if screen is None:
            return

        available_geometry = screen.availableGeometry()
        frame_geometry = self.window.frameGeometry()
        frame_geometry.moveCenter(available_geometry.center())
        self.window.move(frame_geometry.topLeft())

    def destroy_window(self):
        if self.window is None:
            return

        self.closing_by_code = True
        self.window.close()
        self.window = None
        self.closing_by_code = False
        self.process_events()

    def update_frame(self, frame, face_detected):
        if self.window is None:
            return

        self.face_detected = face_detected
        self.buttons = self._get_buttons(self.window_width, self.window_height)
        self.zoom_controls = self._get_zoom_controls(self.window_width, self.window_height)
        self.window.update_frame(frame)
        self.process_events()

    def process_events(self):
        if self.qt_app is not None:
            self.qt_app.processEvents()

    def consume_pending_action(self):
        action = self.pending_action
        self.pending_action = None
        return action


    def set_status_key(self, key):
        self.status_message = t(key)

    def handle_mouse_click(self, x, y):
        zoom_button = self._get_zoom_button_at(x, y)
        if zoom_button == "minus":
            self._change_zoom_by_step(-1)
            save_user_config(self.user_config)
            return

        if zoom_button == "plus":
            self._change_zoom_by_step(1)
            save_user_config(self.user_config)
            return

        for action, rect in self.buttons.items():
            x1, y1, x2, y2 = rect
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.pending_action = action
                return

    def _ensure_qt_app(self):
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        self.qt_app = app

    def _get_buttons(self, width, height):
        button_w = 155
        button_h = 48
        gap = 20

        total_w = button_w * 3 + gap * 2
        start_x = (width - total_w) // 2
        y1 = height - 95
        y2 = y1 + button_h

        return {
            "settings": (start_x, y1, start_x + button_w, y2),
            "calibrate": (start_x + button_w + gap, y1, start_x + button_w * 2 + gap, y2),
            "exit": (start_x + button_w * 2 + gap * 2, y1, start_x + button_w * 3 + gap * 2, y2),
        }

    def _get_zoom_controls(self, width, height):
        panel_w = 210
        panel_h = 56
        x1 = width - panel_w - 45
        y1 = height - panel_h - 150
        x2 = x1 + panel_w
        y2 = y1 + panel_h

        button_size = 38
        margin = 10
        button_y1 = y1 + (panel_h - button_size) // 2
        button_y2 = button_y1 + button_size

        return {
            "bounds": (x1, y1, x2, y2),
            "minus_button": (x1 + margin, button_y1, x1 + margin + button_size, button_y2),
            "plus_button": (x2 - margin - button_size, button_y1, x2 - margin, button_y2),
        }

    def _get_zoom_button_at(self, x, y):
        for name, key in (("minus", "minus_button"), ("plus", "plus_button")):
            rect = self.zoom_controls.get(key)
            if rect and self._point_inside_rect(x, y, rect):
                return name
        return None

    def _point_inside_rect(self, x, y, rect):
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    def _change_zoom_by_step(self, direction):
        step = float(getattr(settings, "CAMERA_DIGITAL_ZOOM_STEP", 0.1))
        if step <= 0:
            step = 0.1

        current_zoom = self.camera.get_digital_zoom()
        new_zoom = current_zoom + step * direction
        new_zoom = max(self.zoom_min, min(new_zoom, self.zoom_max))

        self.camera.set_digital_zoom(new_zoom)
        self.user_config["CAMERA_DIGITAL_ZOOM"] = self.camera.get_digital_zoom()
        self.status_message = t("calibration_zoom_adjusted")