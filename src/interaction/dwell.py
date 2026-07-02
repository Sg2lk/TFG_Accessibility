import time
import math

from src.config import settings
from src.interaction.events import Event


class DwellDetector:
    def __init__(self):
        self.dwell_time = getattr(settings, "DWELL_TIME", 1.2)
        self.move_threshold = getattr(settings, "DWELL_MOVE_THRESHOLD", 35)

        self.cooldown_time = getattr(settings, "DWELL_COOLDOWN_TIME", 0.8)
        self.exit_threshold = getattr(settings, "DWELL_EXIT_THRESHOLD", 55)

        self.require_exit_after_click = getattr(
            settings,
            "DWELL_REQUIRE_EXIT_AFTER_CLICK",
            True
        )

        self.anchor_pos = None
        self.start_time = None

        self.last_click_time = 0
        self.click_pos = None

        self.waiting_for_exit = False

        self.progress = 0.0

    def update(self, x, y):
        if x is None or y is None:
            self.reset()
            return None

        current_pos = (x, y)
        now = time.time()

        if now - self.last_click_time < self.cooldown_time:
            self.progress = 0.0
            return None

        if self.waiting_for_exit:
            if self.click_pos is None:
                self.waiting_for_exit = False
            else:
                distance_from_click = math.dist(
                    current_pos,
                    self.click_pos
                )

                if distance_from_click < self.exit_threshold:
                    self.progress = 0.0
                    return None

                self.waiting_for_exit = False
                self.anchor_pos = current_pos
                self.start_time = None
                self.progress = 0.0
                return None

        if self.anchor_pos is None:
            self.anchor_pos = current_pos
            self.start_time = None
            self.progress = 0.0
            return None

        distance = math.dist(current_pos, self.anchor_pos)

        if distance > self.move_threshold:
            self.anchor_pos = current_pos
            self.start_time = None
            self.progress = 0.0
            return None

        if self.start_time is None:
            self.start_time = now

        elapsed = now - self.start_time

        self.progress = min(elapsed / self.dwell_time, 1.0)

        if elapsed >= self.dwell_time:
            self.last_click_time = now
            self.click_pos = current_pos

            if self.require_exit_after_click:
                self.waiting_for_exit = True

            self.anchor_pos = current_pos
            self.start_time = None
            self.progress = 0.0

            return Event.CLICK_LEFT

        return None

    def reset(self):
        self.anchor_pos = None
        self.start_time = None
        self.click_pos = None

        self.waiting_for_exit = False

        self.progress = 0.0

    def soft_reset(self):
        self.anchor_pos = None
        self.start_time = None

        self.progress = 0.0