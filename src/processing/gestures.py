from src.config import settings
from src.interaction.events import Event


class GestureDetector:
    def __init__(self):
        self.jaw_open_threshold = getattr(
            settings,
            "JAW_OPEN_THRESHOLD",
            0.45
        )

        self.smile_threshold = getattr(
            settings,
            "SMILE_THRESHOLD",
            0.35
        )

        self.eye_closed_threshold = getattr(
            settings,
            "EYE_CLOSED_THRESHOLD",
            0.38
        )

        self.eye_wink_other_eye_max = getattr(
            settings,
            "EYE_WINK_OTHER_EYE_MAX",
            0.24
        )

        self.eyebrows_raised_threshold = getattr(
            settings,
            "EYEBROWS_RAISED_THRESHOLD",
            0.45
        )

    def detect(self, blendshapes=None):
        blendshapes = blendshapes or {}

        if blendshapes:
            return self._detect_with_blendshapes(blendshapes)

        return self._empty_result()

    def _detect_with_blendshapes(self, blendshapes):
        jaw_open_score = blendshapes.get("jawOpen", 0.0)

        smile_left = blendshapes.get("mouthSmileLeft", 0.0)
        smile_right = blendshapes.get("mouthSmileRight", 0.0)
        smile_score = (smile_left + smile_right) / 2.0

        eye_blink_left = blendshapes.get("eyeBlinkLeft", 0.0)
        eye_blink_right = blendshapes.get("eyeBlinkRight", 0.0)

        eyebrow_left = blendshapes.get("browOuterUpLeft", 0.0)
        eyebrow_right = blendshapes.get("browOuterUpRight", 0.0)
        eyebrow_inner = blendshapes.get("browInnerUp", 0.0)
        eyebrows_raised_score = max(
            eyebrow_inner,
            (eyebrow_left + eyebrow_right) / 2.0
        )

        mouth_open = jaw_open_score >= self.jaw_open_threshold
        smile = smile_score >= self.smile_threshold

        mediapipe_wink_left = (
            eye_blink_left >= self.eye_closed_threshold
            and eye_blink_right <= self.eye_wink_other_eye_max
        )

        mediapipe_wink_right = (
            eye_blink_right >= self.eye_closed_threshold
            and eye_blink_left <= self.eye_wink_other_eye_max
        )

        wink_left = mediapipe_wink_right
        wink_right = mediapipe_wink_left

        both_eyes_closed = (
            eye_blink_left >= self.eye_closed_threshold
            and eye_blink_right >= self.eye_closed_threshold
        )

        eye_closed_score = max(eye_blink_left, eye_blink_right)
        eye_closed = wink_left or wink_right or both_eyes_closed

        eyebrows_raised = (
            eyebrows_raised_score >= self.eyebrows_raised_threshold
        )

        gesture = None

        if mouth_open:
            gesture = Event.GESTURE_MOUTH_OPEN
        elif wink_left:
            gesture = Event.GESTURE_WINK_LEFT
        elif wink_right:
            gesture = Event.GESTURE_WINK_RIGHT
        elif eyebrows_raised:
            gesture = Event.GESTURE_EYEBROWS_RAISED
        elif smile:
            gesture = Event.GESTURE_SMILE

        return {
            "gesture": gesture,
            "mouth_open": mouth_open,
            "smile": smile,
            "eye_closed": eye_closed,
            "wink_left": wink_left,
            "wink_right": wink_right,
            "eyebrows_raised": eyebrows_raised,
            "jaw_open_score": jaw_open_score,
            "smile_score": smile_score,
            "eye_blink_left": eye_blink_left,
            "eye_blink_right": eye_blink_right,
            "eye_closed_score": eye_closed_score,
            "eyebrows_raised_score": eyebrows_raised_score,
            "source": "blendshape"
        }

    @staticmethod
    def _empty_result():
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