from enum import Enum


class SystemState(Enum):
    CALIBRATION = "CALIBRATION"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMMAND = "COMMAND"
    SCROLL = "SCROLL"
    DRAG = "DRAG"
