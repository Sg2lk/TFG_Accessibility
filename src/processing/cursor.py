from src.config import settings
from src.platforms.screen import get_primary_screen_size


class CursorProcessor:
    def __init__(self):
        self.screen_width, self.screen_height = get_primary_screen_size()

        self.cursor_x = self.screen_width // 2
        self.cursor_y = self.screen_height // 2

        self.deadzone_x = getattr(settings, "CURSOR_DEADZONE_X", 0.02)
        self.deadzone_y = getattr(settings, "CURSOR_DEADZONE_Y", 0.035)

        self.response_power_x = getattr(settings, "CURSOR_RESPONSE_POWER_X", 1.30)
        self.response_power_y = getattr(settings, "CURSOR_RESPONSE_POWER_Y", 1.55)

    def update(self, yaw, pitch, yaw_center=0.0, pitch_center=0.0):
        if yaw is None or pitch is None:
            return self.cursor_x, self.cursor_y


        yaw_offset = yaw - yaw_center
        pitch_offset = pitch - pitch_center


        yaw_offset = self._apply_deadzone(
            yaw_offset,
            self.deadzone_x
        )

        pitch_offset = self._apply_deadzone(
            pitch_offset,
            self.deadzone_y
        )


        yaw_value = yaw_offset * settings.X_GAIN
        pitch_value = pitch_offset * settings.Y_GAIN


        yaw_value = self._apply_response_curve(
            yaw_value,
            self.response_power_x
        )

        pitch_value = self._apply_response_curve(
            pitch_value,
            self.response_power_y
        )


        self.cursor_x = int((yaw_value + 0.5) * self.screen_width)


        self.cursor_y = int((-pitch_value + 0.5) * self.screen_height)


        self.cursor_x = self._clamp(
            self.cursor_x,
            0,
            self.screen_width+10
        )

        self.cursor_y = self._clamp(
            self.cursor_y,
            0,
            self.screen_height+10
        )

        return self.cursor_x, self.cursor_y

    def reset_to_center(self):
        self.cursor_x = self.screen_width // 2
        self.cursor_y = self.screen_height // 2

        return self.cursor_x, self.cursor_y

    def get_screen_size(self):
        return self.screen_width, self.screen_height

    @staticmethod
    def _apply_deadzone(value, deadzone):
        if abs(value) < deadzone:
            return 0.0

        if value > 0:
            return value - deadzone

        return value + deadzone

    @staticmethod
    def _apply_response_curve(value, power):
        if value == 0:
            return 0.0

        sign = 1 if value > 0 else -1
        magnitude = abs(value)

        return sign * (magnitude ** power)

    @staticmethod
    def _clamp(value, min_value, max_value):
        return max(min_value, min(value, max_value))
