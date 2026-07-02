import logging
import time
from src.config import settings
from src.platforms.screen import get_primary_screen_size
from src.platforms.factory import get_platform
from src.config.user_config import (
    load_and_apply_user_config,
    save_user_config,
    apply_user_config_to_settings
)
from src.actions.action_api import ActionAPI
from src.vision.camera import Camera
from src.vision.face_tracker import FaceTracker
from src.processing.cursor import CursorProcessor
from src.processing.smoothing import PositionSmoother
from src.processing.precision import PrecisionStabilizer
from src.processing.calibration import CalibrationManager
from src.processing.gestures import GestureDetector
from src.interaction.engine import InteractionEngine
from src.interaction.dwell import DwellDetector
from src.interaction.gesture_controller import GestureController
from src.interaction.states import SystemState
from src.interaction.events import Event
from src.interaction.command_menu import CommandMenu
from src.ui.settings_window import open_settings_window
from src.ui.calibration_window import CalibrationWindowController
from src.ui.command_overlay import CommandOverlayManager
from src.ui.keyboard_overlay_manager import KeyboardOverlayManager
from src.i18n import t, gesture_label


logger = logging.getLogger(__name__)

class Application:


    def __init__(self):
        self.user_config = load_and_apply_user_config(settings)

        self.camera = Camera()
        self.tracker = FaceTracker()

        self.calibration = CalibrationManager()
        self.cursor = CursorProcessor()
        self.smoother = PositionSmoother()
        self.precision = PrecisionStabilizer()
        self.gesture_detector = GestureDetector()

        self.interaction = InteractionEngine()
        self.actions = ActionAPI()
        self.dwell = DwellDetector()
        self.gesture_controller = GestureController()

        self.command_menu = CommandMenu()

        self.running = True

        self.smooth_x = 0
        self.smooth_y = 0

        self.last_move_time = 0
        self.move_interval = 0.02

        self.last_scroll_time = 0
        self.scroll_interval = getattr(settings, "SCROLL_INTERVAL", 0.08)

        self.selected_command_option = None

        self.command_target_x = None
        self.command_target_y = None
        self.command_target_locked = False


        self.last_stable_cursor_x = None
        self.last_stable_cursor_y = None


        self.face_lost_start_time = None
        self.face_loss_pause_time = getattr(
            settings,
            "FACE_LOST_PAUSE_TIME",
            1.0
        )

        self.drag_active = False

        self.showing_help_pause = False

        self.screen_width, self.screen_height = get_primary_screen_size()

        self.command_overlay = CommandOverlayManager(enabled=True)
        self.keyboard_overlay = KeyboardOverlayManager()
        self.calibration_window = CalibrationWindowController(
            camera=self.camera,
            user_config=self.user_config
        )

        self.latest_gesture_data = {
            "gesture": None,
            "mouth_open": False,
            "smile": False,
            "eye_closed": False,
            "wink_left": False,
            "wink_right": False,
            "eyebrows_raised": False,
            "jaw_open_score": 0.0,
            "smile_score": 0.0,
            "eye_blink_left": 0.0,
            "eye_blink_right": 0.0,
            "eye_closed_score": 0.0,
            "eyebrows_raised_score": 0.0,
            "source": "none"
        }

    def _refresh_screen_metrics(self):


        self.screen_width, self.screen_height = get_primary_screen_size()
        return self.screen_width, self.screen_height


    def run(self):
        try:
            self._start_components()
            self._run_calibration_loop()

            if self.running:
                self._run_active_loop()

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
            self.running = False

        finally:
            self._shutdown()


    def _start_components(self):
        logger.info("Starting camera")
        self.camera.start()

        logger.info("Starting face tracker")
        self.tracker.start()

        logger.info("Starting Qt command overlay")
        self.command_overlay.start()
        logger.info("Qt command overlay started")

        logger.info("Starting Qt keyboard overlay")
        self.keyboard_overlay.start()
        logger.info("Qt keyboard overlay started")

        logger.info("Components started successfully")

    def _reload_runtime_config(self):


        apply_user_config_to_settings(settings, self.user_config)
        self._refresh_screen_metrics()

        self.scroll_interval = getattr(settings, "SCROLL_INTERVAL", 0.08)
        self.face_loss_pause_time = getattr(
            settings,
            "FACE_LOST_PAUSE_TIME",
            1.0
        )

        self.cursor = CursorProcessor()
        self.smoother = PositionSmoother()
        self.precision = PrecisionStabilizer()
        self.gesture_detector = GestureDetector()
        self.dwell = DwellDetector()
        self.gesture_controller = GestureController()
        self.command_menu = CommandMenu()

        if self.calibration.calibrated:
            center_x = self.screen_width // 2
            center_y = self.screen_height // 2
            self.smoother.reset(center_x, center_y)
            self.precision.reset(center_x, center_y)

        self.calibration_window.refresh_after_config_change(self.user_config)

        self.command_overlay.restart()
        self.keyboard_overlay.restart()

        logger.info("Runtime configuration reloaded")


    def _run_calibration_loop(self):
        logger.info("Calibration started")

        self.interaction.set_state(SystemState.CALIBRATION)
        self.calibration_window.setup_window(self.screen_width, self.screen_height)

        while self.running and not self.calibration.calibrated:
            frame = self.camera.read_frame()

            if frame is None:
                continue

            face_data = self.tracker.detect(frame)

            self.calibration_window.update_frame(
                frame=frame,
                face_detected=bool(face_data and face_data["face_detected"]),
            )

            self._handle_calibration_pending_action(face_data)

        self.calibration_window.destroy_window()

        if self.calibration.calibrated:
            self.interaction.set_state(SystemState.PAUSED)
            self.dwell.reset()
            self.showing_help_pause = True

            logger.info("Calibration completed")
            logger.info("State changed to PAUSED")

            self.command_overlay.show_quick_guide(
                pause_gesture=self._get_pause_gesture_label(),
                command_gesture=self._get_command_gesture_label()
            )

            time.sleep(0.3)
            self._minimize_console_window_if_possible()

    def _handle_calibration_pending_action(self, face_data):
        action = self.calibration_window.consume_pending_action()

        if action is None:
            return

        if action == "calibrate":
            self._try_calibrate(face_data)

        elif action == "settings":
            logger.info("Settings button pressed")
            self._open_settings()
            return

        elif action == "exit":
            self.running = False

    def _open_settings(self):
        in_calibration = (
            self.interaction.state == SystemState.CALIBRATION
            and not self.calibration.calibrated
        )

        updated_config = open_settings_window(self.user_config)

        if updated_config is None:
            self.calibration_window.set_status_key("calibration_settings_unchanged")
            return

        self.user_config = updated_config
        self.calibration_window.set_user_config(self.user_config)
        save_user_config(self.user_config)
        self._reload_runtime_config()

        if in_calibration:
            self._reset_calibration_window()

        self.calibration_window.set_status_key("calibration_settings_saved")

    def _reset_calibration_window(self):
        self.calibration_window.destroy_window()
        self.calibration_window.setup_window(
            self.screen_width,
            self.screen_height,
        )

    def _try_calibrate(self, face_data):
        if not face_data or not face_data["face_detected"]:
            logger.warning("Calibration failed: no face detected")
            self.calibration_window.set_status_key("calibration_no_face")
            return

        success = self.calibration.calibrate(
            face_data["yaw"],
            face_data["pitch"]
        )

        if success:
            self._refresh_screen_metrics()
            center_x = self.screen_width // 2
            center_y = self.screen_height // 2

            self.cursor.reset_to_center()
            self.smoother.reset(center_x, center_y)
            self.precision.reset(center_x, center_y)

            self.smooth_x = center_x
            self.smooth_y = center_y

            self.last_stable_cursor_x = center_x
            self.last_stable_cursor_y = center_y

            self.actions.move_mouse(center_x, center_y)

            self.dwell.reset()

            self.calibration_window.set_status_key("calibration_completed")

            logger.info(
                "User calibrated | yaw_center=%.4f, pitch_center=%.4f, cursor_center=(%s, %s)",
                self.calibration.yaw_center,
                self.calibration.pitch_center,
                center_x,
                center_y,
            )


    def _run_active_loop(self):
        self._refresh_screen_metrics()

        logger.info("Runtime started")

        while self.running:
            frame = self.camera.read_frame()

            if frame is None:
                time.sleep(0.001)
                continue

            face_data = self.tracker.detect(frame)

            self.keyboard_overlay.poll_events(self.dwell)
            self._handle_face_safety(face_data)

            self.latest_gesture_data = self._process_gestures(face_data)
            gesture_event = self.gesture_controller.update(self.latest_gesture_data)

            previous_state = self.interaction.state
            self.interaction.update(dwell_event=None, gesture_event=gesture_event)

            if self.interaction.state != previous_state:
                self.dwell.reset()
                self.selected_command_option = None
                self._handle_state_transition(previous_state, self.interaction.state)

            self._process_state_logic(face_data)

            self.command_overlay.update_for_state(
                state=self.interaction.state,
                selected_option=self.selected_command_option,
                dwell_progress=self.dwell.progress,
                target_x=self.command_target_x,
                target_y=self.command_target_y,
            )

            time.sleep(0.001)


    def _process_state_logic(self, face_data):
        state = self.interaction.state

        if state == SystemState.PAUSED:
            self.dwell.soft_reset()
            return

        if state == SystemState.ACTIVE:
            if self._is_command_gesture_active():


                self._lock_command_target_if_needed()
                self.dwell.soft_reset()
                return

            self._unlock_command_target_if_cancelled()

            self._process_cursor(face_data)


            if self.latest_gesture_data.get("gesture") is None:
                self.last_stable_cursor_x = self.smooth_x
                self.last_stable_cursor_y = self.smooth_y

            self._process_active_mode(face_data)
            return

        if state == SystemState.COMMAND:
            self._process_cursor(face_data)
            self._process_command_mode()
            return

        if state == SystemState.SCROLL:
            self._process_scroll_mode(face_data)
            return

        if state == SystemState.DRAG:
            self._process_cursor(face_data)
            self._process_drag_mode(face_data)
            return

    def _process_active_mode(self, face_data):
        if self.latest_gesture_data.get("gesture") is not None:
            self.dwell.soft_reset()
            return

        if self.keyboard_overlay.is_cursor_inside_protection_area():
            self.dwell.soft_reset()
            return

        dwell_event = self._process_dwell(face_data)

        event = self.interaction.update(
            dwell_event=dwell_event,
            gesture_event=None
        )

        if event == Event.CLICK_LEFT:
            logger.debug("Action: left click")
            self.actions.left_click()

    def _process_command_mode(self):
        if self.latest_gesture_data.get("gesture") is not None:
            self.dwell.soft_reset()
            return


        cursor_x, cursor_y = self.actions.get_mouse_position()

        self.selected_command_option = self.command_menu.get_selected_option(
            cursor_x=cursor_x,
            cursor_y=cursor_y,
            width=self.screen_width,
            height=self.screen_height
        )

        if self.selected_command_option is None:
            self.dwell.soft_reset()
            return

        dwell_event = self.dwell.update(cursor_x, cursor_y)

        if dwell_event == Event.CLICK_LEFT:
            self._execute_command_bar_command(self.selected_command_option)

    def _process_scroll_mode(self, face_data):
        self.dwell.soft_reset()

        if not face_data or not face_data["face_detected"]:
            return

        yaw_center, pitch_center = self.calibration.get_offsets()

        yaw_offset = face_data["yaw"] - yaw_center
        pitch_offset = face_data["pitch"] - pitch_center

        now = time.time()

        if now - self.last_scroll_time < self.scroll_interval:
            return

        vertical_amount = self._calculate_scroll_amount(
            value=pitch_offset,
            deadzone=getattr(settings, "SCROLL_DEADZONE_Y", 0.035),
            gain=getattr(settings, "SCROLL_GAIN_Y", 80),
            max_amount=getattr(settings, "SCROLL_MAX_AMOUNT", 4)
        )

        horizontal_amount = self._calculate_scroll_amount(
            value=yaw_offset,
            deadzone=getattr(settings, "SCROLL_DEADZONE_X", 0.05),
            gain=getattr(settings, "SCROLL_GAIN_X", 60),
            max_amount=getattr(settings, "SCROLL_MAX_AMOUNT", 4)
        )

        if abs(vertical_amount) >= abs(horizontal_amount):
            horizontal_amount = 0
        else:
            vertical_amount = 0

        if vertical_amount != 0:
            self.actions.scroll_vertical(vertical_amount)
            self.last_scroll_time = now

        elif horizontal_amount != 0:
            self.actions.scroll_horizontal(horizontal_amount)
            self.last_scroll_time = now

    def _process_drag_mode(self, face_data):
        if self.latest_gesture_data.get("gesture") is not None:
            self.dwell.soft_reset()
            return

        dwell_event = self._process_dwell(face_data)

        if dwell_event == Event.CLICK_LEFT:
            logger.info("Action: drag release")
            self.actions.left_up()
            self.drag_active = False
            self.command_overlay.show_drag_released()
            self.interaction.set_state(SystemState.ACTIVE)
            self.dwell.reset()
            self._clear_command_target()
            logger.info("State changed to ACTIVE")


    def _store_command_target(self):
        if self.last_stable_cursor_x is not None and self.last_stable_cursor_y is not None:
            self.command_target_x = self.last_stable_cursor_x
            self.command_target_y = self.last_stable_cursor_y
        else:
            self.command_target_x = self.smooth_x
            self.command_target_y = self.smooth_y

        self.command_target_locked = True

    def _clear_command_target(self):
        self.command_target_x = None
        self.command_target_y = None
        self.command_target_locked = False

    def _move_to_command_target(self):
        if self.command_target_x is None or self.command_target_y is None:
            return False

        self.actions.move_mouse(
            self.command_target_x,
            self.command_target_y
        )

        self.smooth_x = self.command_target_x
        self.smooth_y = self.command_target_y

        return True

    def _is_command_gesture_active(self):
        configured_gesture = getattr(
            settings,
            "COMMAND_MENU_GESTURE",
            Event.GESTURE_WINK_LEFT
        )

        return self.latest_gesture_data.get("gesture") == configured_gesture

    def _lock_command_target_if_needed(self):
        if self.command_target_locked:
            return

        if self.last_stable_cursor_x is not None and self.last_stable_cursor_y is not None:
            self.command_target_x = self.last_stable_cursor_x
            self.command_target_y = self.last_stable_cursor_y
        else:
            self.command_target_x = self.smooth_x
            self.command_target_y = self.smooth_y

        self.command_target_locked = True

    def _unlock_command_target_if_cancelled(self):
        if self.interaction.state != SystemState.ACTIVE:
            return

        if self.command_target_locked and not self._is_command_gesture_active():
            self._clear_command_target()

    def _handle_state_transition(self, previous_state, new_state):
        if new_state == SystemState.COMMAND:
            if self.command_target_x is None or self.command_target_y is None:
                self._store_command_target()

        if previous_state == SystemState.COMMAND:
            self.command_overlay.hide()

        if new_state == SystemState.ACTIVE:
            self.showing_help_pause = False
            self.command_overlay.show_status(
                title=t("state_active_title"),
                subtitle=t("state_active_subtitle"),
                kind="success",
                timeout_ms=800
            )

        elif new_state == SystemState.PAUSED:
            if self.showing_help_pause:
                self.command_overlay.show_quick_guide(
                pause_gesture=self._get_pause_gesture_label(),
                command_gesture=self._get_command_gesture_label()
            )
            else:
                self.command_overlay.show_status(
                    title=t("state_paused_title"),
                    subtitle=t(
                        "state_paused_subtitle",
                        pause_gesture=self._get_pause_gesture_label()
                    ),
                    kind="info",
                    timeout_ms=None
                )

        elif new_state == SystemState.SCROLL:
            self.command_overlay.show_status(
                title=t("state_scroll_title"),
                subtitle=t(
                    "state_scroll_subtitle",
                    command_gesture=self._get_command_gesture_label()
                ),
                kind="info",
                timeout_ms=1500
            )

        if new_state not in (
            SystemState.COMMAND,
            SystemState.SCROLL,
            SystemState.DRAG
        ):
            self._clear_command_target()

    def _get_pause_gesture_label(self):
        return gesture_label(
            getattr(settings, "TOGGLE_PAUSE_GESTURE", Event.GESTURE_MOUTH_OPEN)
        )

    def _get_command_gesture_label(self):
        return gesture_label(
            getattr(settings, "COMMAND_MENU_GESTURE", Event.GESTURE_WINK_LEFT)
        )


    def _execute_command_bar_command(self, command):
        if command is None:
            return

        if command == Event.COMMAND_CANCEL:
            logger.info("Command: cancel")
            self._clear_command_target()
            self.interaction.set_state(SystemState.ACTIVE)
            self.command_overlay.hide()
            return

        if command == Event.COMMAND_RIGHT_CLICK:
            logger.info("Command: right click")
            self.command_overlay.hide()

            if self._move_to_command_target():
                self.actions.right_click()

            self._clear_command_target()
            self.interaction.set_state(SystemState.ACTIVE)
            return

        if command == Event.COMMAND_DOUBLE_CLICK:
            logger.info("Command: double click")
            self.command_overlay.hide()

            if self._move_to_command_target():
                self.actions.double_click()

            self._clear_command_target()
            self.interaction.set_state(SystemState.ACTIVE)
            return

        if command == Event.COMMAND_SCROLL:
            logger.info("Command: scroll")
            self.command_overlay.hide()
            self._clear_command_target()
            self.interaction.set_state(SystemState.SCROLL)
            self.command_overlay.show_status(
                title=t("state_scroll_title"),
                subtitle=t(
                    "scroll_help",
                    command_gesture=self._get_command_gesture_label(),
                ),
                kind="info",
                timeout_ms=2500,
            )
            return

        if command == Event.COMMAND_DRAG:
            logger.info("Command: drag")
            self.command_overlay.hide()

            if self._move_to_command_target():
                self.actions.left_down()
                self.drag_active = True
                self.interaction.set_state(SystemState.DRAG)
                self.command_overlay.show_status(
                    title=t("drag_active_title"),
                    subtitle=t("drag_active_subtitle"),
                    kind="drag",
                    timeout_ms=2500,
                )
            else:
                self.interaction.set_state(SystemState.ACTIVE)

            self._clear_command_target()
            return

        if command == Event.COMMAND_KEYBOARD:
            logger.info("Command: keyboard")
            self.command_overlay.hide()
            self.keyboard_overlay.show()
            self._clear_command_target()
            self.interaction.set_state(SystemState.ACTIVE)
            self.command_overlay.show_status(
                title=t("keyboard_title_status"),
                subtitle=t("keyboard_opened"),
                kind="success",
                timeout_ms=1400,
            )
            return

        if command == Event.COMMAND_EXIT:
            logger.info("Command: exit")
            self.command_overlay.hide()
            self.keyboard_overlay.hide()
            self._safe_stop_drag()
            self._clear_command_target()
            self.running = False
            return

        if command == Event.COMMAND_HELP:
            logger.info("Command: help")
            self._clear_command_target()
            self.showing_help_pause = True
            self.interaction.set_state(SystemState.PAUSED)
            self.command_overlay.show_quick_guide(
                pause_gesture=self._get_pause_gesture_label(),
                command_gesture=self._get_command_gesture_label(),
            )
            return


    def _handle_face_safety(self, face_data):


        face_detected = bool(face_data and face_data["face_detected"])

        if face_detected:
            self.face_lost_start_time = None
            return

        state = self.interaction.state

        if state not in (
            SystemState.ACTIVE,
            SystemState.COMMAND,
            SystemState.SCROLL,
            SystemState.DRAG
        ):
            return

        now = time.time()

        if self.face_lost_start_time is None:
            self.face_lost_start_time = now
            return

        elapsed = now - self.face_lost_start_time

        if elapsed < self.face_loss_pause_time:
            return

        logger.warning("Face not detected. System paused.")

        self._safe_stop_drag()
        self.dwell.reset()
        self.selected_command_option = None
        self.command_overlay.hide()
        self._clear_command_target()

        self.showing_help_pause = False
        self.interaction.set_state(SystemState.PAUSED)

        self.command_overlay.show_status(
            title=t("face_missing_title"),
            subtitle=t(
                "face_missing_subtitle",
                pause_gesture=self._get_pause_gesture_label()
            ),
            kind="info",
            timeout_ms=None
        )

        self.face_lost_start_time = None


    def _process_cursor(self, face_data):
        if not face_data or not face_data["face_detected"]:
            self.dwell.soft_reset()
            return

        yaw_center, pitch_center = self.calibration.get_offsets()

        raw_x, raw_y = self.cursor.update(
            yaw=face_data["yaw"],
            pitch=face_data["pitch"],
            yaw_center=yaw_center,
            pitch_center=pitch_center
        )

        smooth_x, smooth_y = self.smoother.update(
            raw_x,
            raw_y
        )

        self.smooth_x, self.smooth_y = self.precision.update(
            smooth_x,
            smooth_y
        )

        now = time.time()

        if now - self.last_move_time > self.move_interval:
            self.actions.move_mouse(self.smooth_x, self.smooth_y)
            self.last_move_time = now

    def _process_dwell(self, face_data):
        if not face_data or not face_data["face_detected"]:
            self.dwell.soft_reset()
            return None

        return self.dwell.update(
            self.smooth_x,
            self.smooth_y
        )

    def _process_gestures(self, face_data):
        if not face_data or not face_data["face_detected"]:
            return {
                "gesture": None,
                "mouth_open": False,
                "smile": False,
                "eye_closed": False,
                "wink_left": False,
                "wink_right": False,
                "eyebrows_raised": False,
                "jaw_open_score": 0.0,
                "smile_score": 0.0,
                "eye_blink_left": 0.0,
                "eye_blink_right": 0.0,
                "eye_closed_score": 0.0,
                "eyebrows_raised_score": 0.0,
                "source": "none"
            }

        return self.gesture_detector.detect(
            blendshapes=face_data.get("blendshapes")
        )

    def _calculate_scroll_amount(self, value, deadzone, gain, max_amount):
        if abs(value) < deadzone:
            return 0

        min_amount = getattr(settings, "SCROLL_MIN_AMOUNT", 4)

        sign = 1 if value > 0 else -1


        magnitude = abs(value) - deadzone


        amount = min_amount + int(magnitude * gain)

        if amount > max_amount:
            amount = max_amount

        return sign * amount

    def _minimize_console_window_if_possible(self):
        if not getattr(settings, "MINIMIZE_CONSOLE_AFTER_CALIBRATION", True):
            return

        get_platform().minimize_console_window()

    def _safe_stop_drag(self):
        if self.interaction.state == SystemState.DRAG or self.drag_active:
            logger.warning("Action: forced drag release")
            self.actions.left_up()
            self.drag_active = False

    def _shutdown(self):
        logger.info("Shutting down")

        self._safe_stop_drag()
        self.command_overlay.stop()
        self.keyboard_overlay.stop()

        self.camera.stop()
        self.tracker.stop()

        logger.info("Shutdown complete")