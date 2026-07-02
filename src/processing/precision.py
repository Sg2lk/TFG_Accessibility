import math

from src.config import settings


class PrecisionStabilizer:
    def __init__(self):
        self.enabled = getattr(settings, "USE_PRECISION_ASSIST", True)

        self.enter_speed = getattr(settings, "PRECISION_ENTER_SPEED", 6)
        self.exit_speed = getattr(settings, "PRECISION_EXIT_SPEED", 45)

        self.stability_frames_required = getattr(
            settings,
            "PRECISION_STABILITY_FRAMES",
            8
        )

        self.alpha = getattr(settings, "PRECISION_ALPHA", 0.18)

        self.micro_deadzone = getattr(
            settings,
            "PRECISION_MICRO_DEADZONE",
            3
        )


        self.use_dynamic_edge_precision = getattr(
            settings,
            "USE_DYNAMIC_EDGE_PRECISION",
            True
        )

        self.edge_extra_enter_speed = getattr(
            settings,
            "PRECISION_EDGE_EXTRA_ENTER_SPEED",
            8
        )

        self.edge_extra_exit_speed = getattr(
            settings,
            "PRECISION_EDGE_EXTRA_EXIT_SPEED",
            35
        )

        self.edge_extra_micro_deadzone = getattr(
            settings,
            "PRECISION_EDGE_EXTRA_MICRO_DEADZONE",
            7
        )

        self.edge_alpha = getattr(
            settings,
            "PRECISION_EDGE_ALPHA",
            0.10
        )

        self.edge_factor_power = getattr(
            settings,
            "PRECISION_EDGE_FACTOR_POWER",
            1.35
        )

        self.active = False

        self.last_x = None
        self.last_y = None

        self.precision_x = None
        self.precision_y = None

        self.center_x = None
        self.center_y = None

        self.stable_frames = 0

    def reset(self, x=None, y=None):
        self.active = False
        self.stable_frames = 0

        self.last_x = x
        self.last_y = y

        self.precision_x = x
        self.precision_y = y

        self.center_x = x
        self.center_y = y

    def update(self, x, y):
        if not self.enabled:
            self.last_x = x
            self.last_y = y
            return int(x), int(y)

        if self.last_x is None or self.last_y is None:
            self.reset(x, y)
            return int(x), int(y)

        edge_factor = self._get_edge_factor(x, y)

        enter_speed = self._get_dynamic_enter_speed(edge_factor)
        exit_speed = self._get_dynamic_exit_speed(edge_factor)
        micro_deadzone = self._get_dynamic_micro_deadzone(edge_factor)
        alpha = self._get_dynamic_alpha(edge_factor)

        movement = math.dist(
            (x, y),
            (self.last_x, self.last_y)
        )

        self.last_x = x
        self.last_y = y

        if movement >= exit_speed:
            self.active = False
            self.stable_frames = 0
            self.precision_x = x
            self.precision_y = y
            return int(x), int(y)

        if movement <= enter_speed:
            self.stable_frames += 1
        else:
            self.stable_frames = max(0, self.stable_frames - 1)

        if self.stable_frames >= self.stability_frames_required:
            self.active = True

        if not self.active:
            self.precision_x = x
            self.precision_y = y
            return int(x), int(y)

        micro_movement = math.dist(
            (x, y),
            (self.precision_x, self.precision_y)
        )

        if micro_movement <= micro_deadzone:
            return int(self.precision_x), int(self.precision_y)

        self.precision_x = (
            self.precision_x * (1.0 - alpha)
            + x * alpha
        )

        self.precision_y = (
            self.precision_y * (1.0 - alpha)
            + y * alpha
        )

        return int(self.precision_x), int(self.precision_y)

    def _get_edge_factor(self, x, y):
        if not self.use_dynamic_edge_precision:
            return 0.0

        if (
            self.center_x is None
            or self.center_y is None
            or self.center_x <= 0
            or self.center_y <= 0
        ):
            return 0.0

        normalized_x = abs(x - self.center_x) / self.center_x
        normalized_y = abs(y - self.center_y) / self.center_y

        raw_factor = math.sqrt(
            normalized_x * normalized_x
            + normalized_y * normalized_y
        )

        raw_factor = max(0.0, min(raw_factor, 1.0))

        return raw_factor ** self.edge_factor_power

    def _get_dynamic_enter_speed(self, edge_factor):
        return (
            self.enter_speed
            + self.edge_extra_enter_speed * edge_factor
        )

    def _get_dynamic_exit_speed(self, edge_factor):
        return (
            self.exit_speed
            + self.edge_extra_exit_speed * edge_factor
        )

    def _get_dynamic_micro_deadzone(self, edge_factor):
        return (
            self.micro_deadzone
            + self.edge_extra_micro_deadzone * edge_factor
        )

    def _get_dynamic_alpha(self, edge_factor):
        return (
            self.alpha * (1.0 - edge_factor)
            + self.edge_alpha * edge_factor
        )