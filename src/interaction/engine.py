import logging

from src.interaction.states import SystemState
from src.interaction.events import Event


logger = logging.getLogger(__name__)


class InteractionEngine:
    def __init__(self):
        self.state = SystemState.ACTIVE

    def set_state(self, state):
        self.state = state

    def toggle_pause(self):
        if self.state == SystemState.PAUSED:
            self.state = SystemState.ACTIVE
            return

        if self.state != SystemState.CALIBRATION:
            self.state = SystemState.PAUSED

    def toggle_command_menu(self):
        if self.state == SystemState.ACTIVE:
            self.state = SystemState.COMMAND
            return

        if self.state == SystemState.COMMAND:
            self.state = SystemState.ACTIVE
            return

        if self.state == SystemState.SCROLL:
            self.state = SystemState.ACTIVE
            return

    def update(self, dwell_event=None, gesture_event=None):
        if gesture_event == Event.TOGGLE_PAUSE:
            self.toggle_pause()
            logger.info("State changed to %s", self.state.value)
            return None

        if gesture_event == Event.OPEN_COMMAND_MENU:
            self.toggle_command_menu()
            logger.info("State changed to %s", self.state.value)
            return None


        if self.state == SystemState.PAUSED:
            return None


        if self.state == SystemState.ACTIVE:
            if dwell_event == Event.CLICK_LEFT:
                return Event.CLICK_LEFT

            return None

        return None
