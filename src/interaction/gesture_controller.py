import time

from src.config import settings
from src.interaction.events import Event


class GestureController:
    def __init__(self):
        self.pause_gesture = (
            Event.from_value(getattr(settings, "TOGGLE_PAUSE_GESTURE", None))
            or Event.GESTURE_MOUTH_OPEN
        )

        self.command_gesture = (
            Event.from_value(getattr(settings, "COMMAND_MENU_GESTURE", None))
            or Event.GESTURE_WINK_LEFT
        )

        self.pause_hold_time = getattr(
            settings,
            "PAUSE_GESTURE_HOLD_TIME",
            1.2
        )

        self.command_hold_time = getattr(
            settings,
            "COMMAND_GESTURE_HOLD_TIME",
            0.4
        )

        self.pause_cooldown_time = getattr(
            settings,
            "PAUSE_GESTURE_COOLDOWN_TIME",
            1.2
        )

        self.command_cooldown_time = getattr(
            settings,
            "COMMAND_GESTURE_COOLDOWN_TIME",
            0.35
        )

        self.current_gesture = None
        self.gesture_start_time = None

        self.last_trigger_times = {
            Event.TOGGLE_PAUSE: 0,
            Event.OPEN_COMMAND_MENU: 0
        }


    def update(self, gesture_data):
        now = time.time()

        gesture = None

        if gesture_data:
            gesture = gesture_data.get("gesture")

        command = self._get_command_for_gesture(gesture)

        if command is None:
            self._reset()
            return None

        hold_time = self._get_hold_time(command)
        cooldown_time = self._get_cooldown_time(command)

        last_trigger_time = self.last_trigger_times.get(command, 0)

        if now - last_trigger_time < cooldown_time:
            return None

        if gesture != self.current_gesture:
            self.current_gesture = gesture
            self.gesture_start_time = now
            return None

        if self.gesture_start_time is None:
            self.gesture_start_time = now

        elapsed = now - self.gesture_start_time

        if elapsed >= hold_time:
            self.last_trigger_times[command] = now
            self._reset()
            return command

        return None

    def _get_command_for_gesture(self, gesture):
        if gesture == self.pause_gesture:
            return Event.TOGGLE_PAUSE

        if gesture == self.command_gesture:
            return Event.OPEN_COMMAND_MENU

        return None

    def _get_hold_time(self, command):
        if command == Event.TOGGLE_PAUSE:
            return self.pause_hold_time

        if command == Event.OPEN_COMMAND_MENU:
            return self.command_hold_time

        return 1.0

    def _get_cooldown_time(self, command):
        if command == Event.TOGGLE_PAUSE:
            return self.pause_cooldown_time

        if command == Event.OPEN_COMMAND_MENU:
            return self.command_cooldown_time

        return 1.0

    def _reset(self):
        self.current_gesture = None
        self.gesture_start_time = None