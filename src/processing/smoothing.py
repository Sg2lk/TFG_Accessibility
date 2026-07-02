from src.config import settings
from src.platforms.screen import get_primary_screen_size


class PositionSmoother:
    def __init__(self):
        self.screen_width, self.screen_height = get_primary_screen_size()

        self.x = self.screen_width // 2
        self.y = self.screen_height // 2

        self.initialized = False


        self.min_alpha_x = getattr(settings, "SMOOTHING_MIN_ALPHA_X", 0.08)
        self.max_alpha_x = getattr(settings, "SMOOTHING_MAX_ALPHA_X", 0.35)

        self.precision_distance_x = getattr(
            settings,
            "SMOOTHING_PRECISION_DISTANCE_X",
            8
        )

        self.fast_distance_x = getattr(
            settings,
            "SMOOTHING_FAST_DISTANCE_X",
            160
        )


        self.min_alpha_y = getattr(settings, "SMOOTHING_MIN_ALPHA_Y", 0.04)
        self.max_alpha_y = getattr(settings, "SMOOTHING_MAX_ALPHA_Y", 0.22)

        self.precision_distance_y = getattr(
            settings,
            "SMOOTHING_PRECISION_DISTANCE_Y",
            14
        )

        self.fast_distance_y = getattr(
            settings,
            "SMOOTHING_FAST_DISTANCE_Y",
            220
        )


        self.max_y_step = getattr(settings, "SMOOTHING_MAX_Y_STEP", 18)

        self.use_adaptive = getattr(
            settings,
            "USE_ADAPTIVE_SMOOTHING",
            True
        )

    def update(self, target_x, target_y):
        if target_x is None or target_y is None:
            return self.x, self.y

        target_x = int(target_x)
        target_y = int(target_y)

        if not self.initialized:
            self.x = target_x
            self.y = target_y
            self.initialized = True
            return self.x, self.y

        dx = target_x - self.x
        dy = target_y - self.y

        if self.use_adaptive:
            alpha_x = self._calculate_adaptive_alpha(
                distance=abs(dx),
                min_alpha=self.min_alpha_x,
                max_alpha=self.max_alpha_x,
                precision_distance=self.precision_distance_x,
                fast_distance=self.fast_distance_x
            )

            alpha_y = self._calculate_adaptive_alpha(
                distance=abs(dy),
                min_alpha=self.min_alpha_y,
                max_alpha=self.max_alpha_y,
                precision_distance=self.precision_distance_y,
                fast_distance=self.fast_distance_y
            )
        else:
            alpha_x = getattr(settings, "SMOOTHING", 0.2)
            alpha_y = getattr(settings, "SMOOTHING", 0.2)

        new_x = round(alpha_x * target_x + (1 - alpha_x) * self.x)
        new_y = round(alpha_y * target_y + (1 - alpha_y) * self.y)


        new_y = self._limit_step(
            current=self.y,
            target=new_y,
            max_step=self.max_y_step
        )

        self.x = int(new_x)
        self.y = int(new_y)

        return self.x, self.y

    def reset(self, x=None, y=None):
        self.x = int(x if x is not None else self.screen_width // 2)
        self.y = int(y if y is not None else self.screen_height // 2)

        self.initialized = True

        return self.x, self.y

    def get_screen_size(self):
        return self.screen_width, self.screen_height

    @staticmethod
    def _calculate_adaptive_alpha(
        distance,
        min_alpha,
        max_alpha,
        precision_distance,
        fast_distance
    ):
        if distance <= precision_distance:
            return min_alpha

        if distance >= fast_distance:
            return max_alpha

        ratio = (
            (distance - precision_distance)
            / (fast_distance - precision_distance)
        )

        return min_alpha + ratio * (max_alpha - min_alpha)

    @staticmethod
    def _limit_step(current, target, max_step):
        delta = target - current

        if delta > max_step:
            return current + max_step

        if delta < -max_step:
            return current - max_step

        return target
