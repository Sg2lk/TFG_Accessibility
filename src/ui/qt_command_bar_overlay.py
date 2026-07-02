import multiprocessing
import queue
import sys


class QtCommandBarOverlayController:
    def __init__(self):
        self.ctx = multiprocessing.get_context("spawn")
        self.command_queue = self.ctx.Queue()
        self.process = None

    def start(self):
        if self.process is not None and self.process.is_alive():
            return

        self.process = self.ctx.Process(
            target=_run_qt_overlay_process,
            args=(self.command_queue,),
            daemon=True,
        )
        self.process.start()

    def show(self, selected_option=None, dwell_progress=0.0, target_x=None, target_y=None):
        self.command_queue.put({
            "type": "show_menu",
            "selected_option": selected_option,
            "dwell_progress": dwell_progress,
            "target_x": target_x,
            "target_y": target_y,
        })

    def update(self, selected_option=None, dwell_progress=0.0, target_x=None, target_y=None):
        self.command_queue.put({
            "type": "update_menu",
            "selected_option": selected_option,
            "dwell_progress": dwell_progress,
            "target_x": target_x,
            "target_y": target_y,
        })

    def hide(self):
        self.command_queue.put({"type": "hide"})

    def show_status(self, title, subtitle="", kind="info", timeout_ms=None):
        self.command_queue.put({
            "type": "show_status",
            "title": title,
            "subtitle": subtitle,
            "kind": kind,
            "timeout_ms": timeout_ms,
        })

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


def _run_qt_overlay_process(command_queue):
    from PySide6.QtCore import Qt, QTimer, QRectF
    from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QFont
    from PySide6.QtWidgets import QApplication, QWidget

    from src.config import settings
    from src.config.user_config import load_and_apply_user_config
    from src.i18n import t
    from src.interaction.command_menu import CommandMenu
    from src.platforms.screen import get_primary_screen_size

    load_and_apply_user_config(settings)

    class CommandBarWindow(QWidget):
        def __init__(self):
            super().__init__()

            self.command_menu = CommandMenu()
            self.mode = "hidden"

            self.selected_option = None
            self.dwell_progress = 0.0
            self.target_x = None
            self.target_y = None

            self.status_title = ""
            self.status_subtitle = ""
            self.status_kind = "info"
            self.status_token = 0

            self.setWindowFlags(
                Qt.FramelessWindowHint
                | Qt.WindowStaysOnTopHint
                | Qt.Tool
            )
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            self.setAttribute(Qt.WA_TransparentForMouseEvents)
            self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)

            screen = QApplication.primaryScreen()
            geometry = screen.geometry()
            self.screen_width = geometry.width()
            self.screen_height = geometry.height()
            self.physical_screen_width, self.physical_screen_height = get_primary_screen_size()
            self.coord_scale_x = self.screen_width / max(1, self.physical_screen_width)
            self.coord_scale_y = self.screen_height / max(1, self.physical_screen_height)

            self.setGeometry(0, 0, self.screen_width, self.screen_height)
            self.hide()

        def _to_qt_coordinates(self, x, y):
            if x is None or y is None:
                return None, None
            return int(round(x * self.coord_scale_x)), int(round(y * self.coord_scale_y))

        def show_menu(self, selected_option=None, dwell_progress=0.0, target_x=None, target_y=None):
            self.mode = "menu"
            self.selected_option = selected_option
            self.dwell_progress = max(0.0, min(float(dwell_progress), 1.0))
            self.target_x = target_x
            self.target_y = target_y
            self.update()
            self.show()

        def update_menu(self, selected_option=None, dwell_progress=0.0, target_x=None, target_y=None):
            self.show_menu(selected_option, dwell_progress, target_x, target_y)

        def show_status(self, title, subtitle="", kind="info", timeout_ms=None):
            self.mode = "status"
            self.status_title = title
            self.status_subtitle = subtitle
            self.status_kind = kind
            self.status_token += 1
            token = self.status_token
            self.update()
            self.show()

            if timeout_ms is not None:
                def hide_current_status():
                    self._hide_status_if_current(token)

                QTimer.singleShot(timeout_ms, hide_current_status)

        def hide_overlay(self):
            self.mode = "hidden"
            self.hide()

        def _hide_status_if_current(self, token):
            if self.mode == "status" and token == self.status_token:
                self.hide_overlay()

        def paintEvent(self, event):
            painter = QPainter(self)

            if self.mode == "menu":
                self._draw_target_marker(painter)
                self._draw_command_bar(painter)
            elif self.mode == "status":
                self._draw_status_box(painter)

        def _draw_target_marker(self, painter):
            x, y = self._to_qt_coordinates(self.target_x, self.target_y)
            if x is None or y is None:
                return

            painter.setPen(QPen(QColor(255, 180, 0), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(x - 14, y - 14, 28, 28)
            painter.drawLine(x - 20, y, x + 20, y)
            painter.drawLine(x, y - 20, x, y + 20)

        def _draw_command_bar(self, painter):
            rects = self.command_menu.get_option_rects(
                self.physical_screen_width,
                self.physical_screen_height,
            )

            title_y_physical = (
                self.physical_screen_height // 2
                - self.command_menu.option_height // 2
                - 34
            )
            _, y_title = self._to_qt_coordinates(0, title_y_physical)

            painter.setFont(QFont("Arial", 14, QFont.Bold))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                QRectF(0, y_title, self.screen_width, 28),
                Qt.AlignCenter,
                f"{t('cmd_center_title')} - {t('cmd_center_subtitle')}",
            )

            for option in self.command_menu.options:
                option_id = option["id"]
                label = option["label"]
                x1, y1, x2, y2 = rects[option_id]

                qx1, qy1 = self._to_qt_coordinates(x1, y1)
                qx2, qy2 = self._to_qt_coordinates(x2, y2)
                w = qx2 - qx1
                h = qy2 - qy1
                selected = option_id == self.selected_option

                fill = QColor(70, 90, 150) if selected else QColor(45, 45, 45)
                border = QColor(0, 220, 220) if selected else QColor(220, 220, 220)

                painter.setBrush(QBrush(fill))
                painter.setPen(QPen(border, 2))
                painter.drawRect(qx1, qy1, w, h)

                if selected:
                    progress_w = int(w * self.dwell_progress)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(0, 220, 220))
                    painter.drawRect(qx1, qy2 - 8, progress_w, 8)

                painter.setFont(QFont("Arial", 11, QFont.Bold))
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(QRectF(qx1, qy1, w, h - 8), Qt.AlignCenter, str(label))

        def _draw_status_box(self, painter):
            lines = str(self.status_subtitle).split("\n") if self.status_subtitle else []
            box_w = 560
            line_h = 24
            box_h = 74 + max(1, len(lines)) * line_h
            x = self.screen_width // 2 - box_w // 2
            y = 70

            if self.status_kind == "success":
                border = QColor(0, 180, 90)
            elif self.status_kind == "drag":
                border = QColor(255, 170, 0)
            else:
                border = QColor(220, 220, 220)

            painter.setBrush(QBrush(QColor(35, 35, 35)))
            painter.setPen(QPen(border, 2))
            painter.drawRect(x, y, box_w, box_h)

            painter.setFont(QFont("Arial", 16, QFont.Bold))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(QRectF(x + 16, y + 14, box_w - 32, 30), Qt.AlignCenter, self.status_title)

            painter.setFont(QFont("Arial", 11))
            text_y = y + 55
            for line in lines:
                painter.drawText(QRectF(x + 24, text_y, box_w - 48, line_h), Qt.AlignLeft, line)
                text_y += line_h

    app = QApplication(sys.argv)
    window = CommandBarWindow()

    def poll_queue():
        while True:
            try:
                message = command_queue.get_nowait()
            except queue.Empty:
                break

            message_type = message.get("type")

            if message_type == "show_menu":
                window.show_menu(
                    selected_option=message.get("selected_option"),
                    dwell_progress=message.get("dwell_progress", 0.0),
                    target_x=message.get("target_x"),
                    target_y=message.get("target_y"),
                )
            elif message_type == "update_menu":
                window.update_menu(
                    selected_option=message.get("selected_option"),
                    dwell_progress=message.get("dwell_progress", 0.0),
                    target_x=message.get("target_x"),
                    target_y=message.get("target_y"),
                )
            elif message_type == "show_status":
                window.show_status(
                    title=message.get("title", ""),
                    subtitle=message.get("subtitle", ""),
                    kind=message.get("kind", "info"),
                    timeout_ms=message.get("timeout_ms"),
                )
            elif message_type == "hide":
                window.hide_overlay()
            elif message_type == "close":
                window.close()
                app.quit()

    timer = QTimer()
    timer.timeout.connect(poll_queue)
    timer.start(16)
    app.exec()
