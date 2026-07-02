from pathlib import Path
import sys
import time

import mediapipe as mp

from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class FaceTracker:
    def __init__(self, model_path=None):
        self.model_path = self._resolve_model_path(model_path)
        self.landmarker = None

    def start(self):
        base_options = python.BaseOptions(
            model_asset_path=str(self.model_path)
        )

        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1
        )

        self.landmarker = vision.FaceLandmarker.create_from_options(options)

    def detect(self, frame, timestamp_ms=None):
        if self.landmarker is None:
            raise RuntimeError(
                "FaceTracker no inicializado. Llama a start() primero"
            )

        if frame is None:
            return None

        rgb_frame = frame[..., ::-1]

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame
        )

        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        result = self.landmarker.detect_for_video(
            mp_image,
            timestamp_ms
        )

        if not result.face_landmarks:
            return {
                "face_detected": False,
                "landmarks": None,
                "blendshapes": {},
                "yaw": None,
                "pitch": None
            }

        landmarks = result.face_landmarks[0]

        yaw = None
        pitch = None

        if result.facial_transformation_matrixes:
            matrix = result.facial_transformation_matrixes[0]

            yaw = float(matrix[0][2])
            pitch = float(matrix[1][2])

        blendshapes = self._extract_blendshapes(result)

        return {
            "face_detected": True,
            "landmarks": landmarks,
            "blendshapes": blendshapes,
            "yaw": yaw,
            "pitch": pitch
        }

    def _extract_blendshapes(self, result):
        if not result.face_blendshapes:
            return {}

        face_blendshapes = result.face_blendshapes[0]

        blendshape_dict = {}

        for category in face_blendshapes:
            blendshape_dict[category.category_name] = float(
                category.score
            )

        return blendshape_dict

    def stop(self):
        if self.landmarker:
            self.landmarker.close()
            self.landmarker = None

    @staticmethod
    def _resolve_model_path(model_path=None):
        if model_path is None:
            model_path = Path("models") / "face_landmarker.task"
        else:
            model_path = Path(model_path)

        if model_path.is_absolute():
            return model_path

        return FaceTracker._get_resource_base_path() / model_path

    @staticmethod
    def _get_resource_base_path():
        if getattr(sys, "frozen", False):
            return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))

        return Path(__file__).resolve().parents[2]
