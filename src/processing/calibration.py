class CalibrationManager:
    def __init__(self):
        self.yaw_center = 0.0
        self.pitch_center = 0.0
        self.calibrated = False

    def calibrate(self, yaw, pitch):
        if yaw is None or pitch is None:
            return False

        self.yaw_center = yaw
        self.pitch_center = pitch
        self.calibrated = True

        return True

    def reset(self):
        self.yaw_center = 0.0
        self.pitch_center = 0.0
        self.calibrated = False

    def get_offsets(self):
        return self.yaw_center, self.pitch_center
