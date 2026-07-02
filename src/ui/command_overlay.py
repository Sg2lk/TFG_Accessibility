from src.interaction.states import SystemState
from src.i18n import t
from src.ui.qt_command_bar_overlay import QtCommandBarOverlayController


class CommandOverlayManager:


    def __init__(self, enabled=True):
        self.enabled = enabled
        self.overlay = None
        self.menu_visible = False

    def start(self):
        if not self.enabled:
            return

        self.overlay = QtCommandBarOverlayController()
        self.overlay.start()

    def stop(self):
        self.hide()
        if self.overlay:
            self.overlay.stop()
            self.overlay = None

    def restart(self):
        if not self.enabled:
            return
        self.stop()
        self.start()

    def hide(self):
        if self.overlay and self.menu_visible:
            self.overlay.hide()
        self.menu_visible = False

    def update_for_state(
        self,
        state,
        selected_option=None,
        dwell_progress=0.0,
        target_x=None,
        target_y=None,
    ):
        if not self.overlay:
            return

        if state == SystemState.COMMAND:
            if not self.menu_visible:
                self.overlay.show(
                    selected_option=selected_option,
                    dwell_progress=dwell_progress,
                    target_x=target_x,
                    target_y=target_y,
                )
                self.menu_visible = True
            else:
                self.overlay.update(
                    selected_option=selected_option,
                    dwell_progress=dwell_progress,
                    target_x=target_x,
                    target_y=target_y,
                )
            return

        self.hide()

    def show_status(self, title, subtitle="", kind="info", timeout_ms=1000):
        self.menu_visible = False

        if self.overlay:
            self.overlay.show_status(
                title=title,
                subtitle=subtitle,
                kind=kind,
                timeout_ms=timeout_ms,
            )

    def show_quick_guide(self, pause_gesture, command_gesture):
        self.show_status(
            title=t("quick_guide_title"),
            subtitle=t(
                "quick_guide_subtitle",
                pause_gesture=pause_gesture,
                command_gesture=command_gesture,
            ),
            kind="info",
            timeout_ms=None,
        )


    def show_drag_released(self):
        self.show_status(
            title=t("drag_released_title"),
            subtitle=t("drag_released_subtitle"),
            kind="success",
            timeout_ms=900,
        )
