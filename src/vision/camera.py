import cv2
from src.config import settings


class Camera:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.cap = None
        self.digital_zoom = float(getattr(settings, "CAMERA_DIGITAL_ZOOM", 1.0))

    def start(self):
        self.cap = cv2.VideoCapture(self.camera_index)

        self._set_capture_property_if_configured(
            cv2.CAP_PROP_FRAME_WIDTH,
            getattr(settings, "CAMERA_WIDTH", None)
        )
        self._set_capture_property_if_configured(
            cv2.CAP_PROP_FRAME_HEIGHT,
            getattr(settings, "CAMERA_HEIGHT", None)
        )

        self._try_set_hardware_zoom(self.digital_zoom)

        if not self.cap.isOpened():
            raise RuntimeError("No se pudo abrir la cámara")


    def _set_capture_property_if_configured(self, prop, value):
        if self.cap is None or value is None:
            return

        try:
            value = int(value)
        except (TypeError, ValueError):
            return

        if value <= 0:
            return

        self.cap.set(prop, value)

    def set_digital_zoom(self, zoom):
        min_zoom = float(getattr(settings, "CAMERA_DIGITAL_ZOOM_MIN", 1.0))
        max_zoom = float(getattr(settings, "CAMERA_DIGITAL_ZOOM_MAX", 2.5))

        self.digital_zoom = max(min_zoom, min(float(zoom), max_zoom))
        setattr(settings, "CAMERA_DIGITAL_ZOOM", self.digital_zoom)

        self._try_set_hardware_zoom(self.digital_zoom)

    def get_digital_zoom(self):
        return self.digital_zoom

    def read_frame(self):
        if self.cap is None:
            raise RuntimeError("Camera no inicializada. Llama a start() primero")

        ret, frame = self.cap.read()

        if not ret:
            return None

        frame = self._apply_digital_zoom(frame)


        frame = cv2.flip(frame, 1)

        return frame

    def _apply_digital_zoom(self, frame):
        zoom = max(1.0, float(self.digital_zoom))

        if zoom <= 1.01:
            return frame

        height, width = frame.shape[:2]

        crop_width = max(1, int(width / zoom))
        crop_height = max(1, int(height / zoom))

        x1 = (width - crop_width) // 2
        y1 = (height - crop_height) // 2
        x2 = x1 + crop_width
        y2 = y1 + crop_height

        cropped = frame[y1:y2, x1:x2]

        return cv2.resize(
            cropped,
            (width, height),
            interpolation=cv2.INTER_LINEAR
        )

    def _try_set_hardware_zoom(self, zoom):
        if self.cap is None:
            return

        try:
            self.cap.set(cv2.CAP_PROP_ZOOM, float(zoom))
        except Exception:
            pass

    def stop(self):
        if self.cap:
            self.cap.release()
            self.cap = None