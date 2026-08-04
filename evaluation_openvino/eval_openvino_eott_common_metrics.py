import argparse
import csv
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean

import cv2
import numpy as np
import openvino as ov


BASE_DIR = Path(__file__).resolve().parent

DEFAULT_DATASET_ROOT = (
    Path.home()
    / "OneDrive"
    / "Documents"
    / "TFG"
    / "DataSet"
    / "EOTT"
    / "WebGazerETRA2018Dataset_Release20180420"
)
DEFAULT_MODELS_DIR = BASE_DIR / "openvino_models" / "intel"
RESULTS_CSV = BASE_DIR / "resultados.csv"
VIDEO_EXTENSIONS = {".webm", ".mp4"}

CABECERA_CSV = [
    "Ejecución",
    "Salto angular medio (grados)",
    "Salto angular p95 (grados)",
    "Saltos > 10 grados",
    "Saltos > 15 grados",
]

CABECERA_ANTERIOR = CABECERA_CSV[1:]


def build_model_paths(models_dir):
    return {
        "face": models_dir / "face-detection-adas-0001/FP32/face-detection-adas-0001.xml",
        "landmarks": models_dir / "facial-landmarks-35-adas-0002/FP32/facial-landmarks-35-adas-0002.xml",
        "headpose": models_dir / "head-pose-estimation-adas-0001/FP32/head-pose-estimation-adas-0001.xml",
        "gaze": models_dir / "gaze-estimation-adas-0002/FP32/gaze-estimation-adas-0002.xml",
    }


def check_models(model_paths):
    missing = [str(path) for path in model_paths.values() if not path.exists()]

    if missing:
        raise FileNotFoundError("Faltan modelos OpenVINO:\n" + "\n".join(f"- {path}" for path in missing))


def parse_participant(path):
    for part in path.parts:
        if part.upper().startswith("P_"):
            return part

    return path.parent.name


def collect_videos(root, extensions):
    if not root.exists():
        raise FileNotFoundError(f"No existe la ruta del dataset: {root}")

    normalized_extensions = {
        extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        for extension in extensions
    }

    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in normalized_extensions
    )


def select_balanced_videos(video_paths, videos_per_participant, max_participants, max_videos, seed):
    rng = random.Random(seed) if seed is not None else random.Random()
    groups = defaultdict(list)

    for path in video_paths:
        groups[parse_participant(path)].append(path)

    participants = sorted(groups)
    rng.shuffle(participants)

    if max_participants and max_participants > 0:
        participants = participants[:max_participants]

    selected = []

    for participant in participants:
        paths = list(groups[participant])
        rng.shuffle(paths)
        selected.extend(paths[:videos_per_participant])

    rng.shuffle(selected)

    if max_videos and max_videos > 0:
        selected = selected[:max_videos]

    return selected


def preprocess(frame, input_tensor):
    _, channels, height, width = list(input_tensor.shape)
    resized = cv2.resize(frame, (width, height))
    blob = resized.transpose(2, 0, 1) if channels == 3 else resized
    return np.expand_dims(blob, axis=0).astype(np.float32)


def first_output(result):
    return next(iter(result.values()))


def infer_single_input(compiled_model, frame):
    return compiled_model([preprocess(frame, compiled_model.inputs[0])])


def clamp_box(x1, y1, x2, y2, width, height):
    x1 = max(0, min(width - 1, int(x1)))
    y1 = max(0, min(height - 1, int(y1)))
    x2 = max(0, min(width - 1, int(x2)))
    y2 = max(0, min(height - 1, int(y2)))

    if x2 <= x1 or y2 <= y1:
        return None

    return x1, y1, x2, y2


def crop_box(frame, box):
    x1, y1, x2, y2 = box
    return frame[y1:y2, x1:x2].copy()


def get_face_bbox(face_result, frame_width, frame_height, confidence_threshold):
    detections = first_output(face_result)[0][0]
    best_box = None
    best_confidence = 0.0

    for detection in detections:
        confidence = float(detection[2])

        if confidence < confidence_threshold:
            continue

        box = clamp_box(
            detection[3] * frame_width,
            detection[4] * frame_height,
            detection[5] * frame_width,
            detection[6] * frame_height,
            frame_width,
            frame_height,
        )

        if box is not None and confidence > best_confidence:
            best_box = box
            best_confidence = confidence

    return best_box


def get_landmarks(landmarks_result, face_box):
    output = first_output(landmarks_result).reshape(-1)
    x1, y1, x2, y2 = face_box
    face_width = x2 - x1
    face_height = y2 - y1

    return [
        (
            x1 + int(output[index] * face_width),
            y1 + int(output[index + 1] * face_height),
        )
        for index in range(0, len(output), 2)
    ]


def square_eye_crop(frame, point_a, point_b, scale=2.2):
    frame_height, frame_width = frame.shape[:2]
    center_x = int((point_a[0] + point_b[0]) / 2)
    center_y = int((point_a[1] + point_b[1]) / 2)
    eye_width = float(np.hypot(point_a[0] - point_b[0], point_a[1] - point_b[1]))
    size = int(max(28, eye_width * scale))

    box = clamp_box(
        center_x - size // 2,
        center_y - size // 2,
        center_x + size // 2,
        center_y + size // 2,
        frame_width,
        frame_height,
    )

    if box is None:
        return None

    crop = crop_box(frame, box)
    return crop if crop.size else None


def get_head_pose(headpose_result):
    values = {
        output.get_any_name(): float(value.reshape(-1)[0])
        for output, value in headpose_result.items()
    }

    yaw = values.get("angle_y_fc", values.get("fc_y", 0.0))
    pitch = values.get("angle_p_fc", values.get("fc_p", 0.0))
    roll = values.get("angle_r_fc", values.get("fc_r", 0.0))

    return np.array([[yaw, pitch, roll]], dtype=np.float32)


def angular_distance_deg(vector_a, vector_b):
    vector_a = np.asarray(vector_a, dtype=np.float64)
    vector_b = np.asarray(vector_b, dtype=np.float64)
    norm_a = np.linalg.norm(vector_a)
    norm_b = np.linalg.norm(vector_b)

    if norm_a == 0 or norm_b == 0:
        return None

    cosine = float(np.dot(vector_a, vector_b) / (norm_a * norm_b))
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def percentile(values, percentage):
    ordered = sorted(values)

    if not ordered:
        return 0.0

    if len(ordered) == 1:
        return float(ordered[0])

    index = (len(ordered) - 1) * (percentage / 100.0)
    lower = int(math.floor(index))
    upper = int(math.ceil(index))

    if lower == upper:
        return float(ordered[lower])

    return float(
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * (index - lower)
    )


def process_frame(frame, models, face_confidence):
    frame_height, frame_width = frame.shape[:2]

    try:
        face_result = infer_single_input(models["face"], frame)
        face_box = get_face_bbox(face_result, frame_width, frame_height, face_confidence)

        if face_box is None:
            return None

        face_crop = crop_box(frame, face_box)
        landmarks_result = infer_single_input(models["landmarks"], face_crop)
        landmarks = get_landmarks(landmarks_result, face_box)

        headpose_result = infer_single_input(models["headpose"], face_crop)
        head_angles = get_head_pose(headpose_result)

        left_eye = square_eye_crop(frame, landmarks[0], landmarks[1])
        right_eye = square_eye_crop(frame, landmarks[2], landmarks[3])

        if left_eye is None or right_eye is None:
            return None

        gaze_result = models["gaze"]({
            "left_eye_image": preprocess(left_eye, models["gaze"].input("left_eye_image")),
            "right_eye_image": preprocess(right_eye, models["gaze"].input("right_eye_image")),
            "head_pose_angles": head_angles,
        })

        return first_output(gaze_result).reshape(-1)

    except Exception:
        return None


def process_video(video_path, models, args):
    capture = cv2.VideoCapture(str(video_path))

    if not capture.isOpened():
        raise RuntimeError(f"No se pudo abrir el vídeo: {video_path}")

    frame_index = 0
    sampled_frames = 0
    previous_gaze = None
    gaze_jumps = []

    try:
        while True:
            success, frame = capture.read()

            if not success:
                break

            if frame_index < args.skip_initial_frames:
                frame_index += 1
                continue

            if frame_index % args.frame_step == 0:
                current_gaze = process_frame(frame, models, args.face_conf)
                sampled_frames += 1

                if current_gaze is None:
                    previous_gaze = None
                else:
                    if previous_gaze is not None:
                        jump = angular_distance_deg(previous_gaze, current_gaze)

                        if jump is not None:
                            gaze_jumps.append(jump)

                    previous_gaze = current_gaze

                if args.max_frames_per_video and sampled_frames >= args.max_frames_per_video:
                    break

            frame_index += 1

    finally:
        capture.release()

    return gaze_jumps


def csv_number(value):
    return f"{value:.2f}".replace(".", ",")


def prepare_existing_csv():
    if not RESULTS_CSV.exists() or RESULTS_CSV.stat().st_size == 0:
        return

    with RESULTS_CSV.open("r", newline="", encoding="utf-8-sig") as csv_file:
        rows = list(csv.reader(csv_file, delimiter=";"))

    if not rows or rows[0] == CABECERA_CSV:
        return

    if rows[0] != CABECERA_ANTERIOR:
        raise RuntimeError(
            "El CSV existente no tiene un formato compatible. "
            "Renómbralo o elimínalo antes de continuar."
        )

    updated_rows = [CABECERA_CSV]

    for execution, row in enumerate(rows[1:], 1):
        if any(cell.strip() for cell in row):
            updated_rows.append([execution, *row])

    with RESULTS_CSV.open("w", newline="", encoding="utf-8-sig") as csv_file:
        csv.writer(csv_file, delimiter=";").writerows(updated_rows)


def get_execution_number():
    prepare_existing_csv()

    if not RESULTS_CSV.exists() or RESULTS_CSV.stat().st_size == 0:
        return 1

    executions = []

    with RESULTS_CSV.open("r", newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")

        for row in reader:
            try:
                executions.append(int((row.get("Ejecución") or "").strip()))
            except ValueError:
                continue

    return max(executions, default=0) + 1


def save_results(gaze_jumps):
    prepare_existing_csv()
    file_exists = RESULTS_CSV.exists() and RESULTS_CSV.stat().st_size > 0
    execution = get_execution_number()

    row = [
        execution,
        csv_number(mean(gaze_jumps)),
        csv_number(percentile(gaze_jumps, 95)),
        sum(value > 10 for value in gaze_jumps),
        sum(value > 15 for value in gaze_jumps),
    ]

    with RESULTS_CSV.open("a", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file, delimiter=";")

        if not file_exists:
            writer.writerow(CABECERA_CSV)

        writer.writerow(row)


def read_arguments():
    parser = argparse.ArgumentParser(
        description="Evalúa la estabilidad temporal de la estimación de mirada con OpenVINO sobre EOTT."
    )
    parser.add_argument("--dataset-root", type=Path, default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--models-dir", type=Path, default=DEFAULT_MODELS_DIR)
    parser.add_argument("--videos-per-participant", type=int, default=2)
    parser.add_argument("--max-participants", type=int, default=6)
    parser.add_argument("--max-videos", type=int, default=0)
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--max-frames-per-video", type=int, default=300)
    parser.add_argument("--skip-initial-frames", type=int, default=30)
    parser.add_argument("--face-conf", type=float, default=0.45)
    parser.add_argument("--extensions", nargs="+", default=sorted(VIDEO_EXTENSIONS))
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main():
    args = read_arguments()

    try:
        if args.frame_step < 1:
            raise ValueError("--frame-step debe ser igual o superior a 1.")

        all_videos = collect_videos(args.dataset_root, args.extensions)
        selected_videos = select_balanced_videos(
            all_videos,
            args.videos_per_participant,
            args.max_participants,
            args.max_videos,
            args.seed,
        )

        if not selected_videos:
            raise RuntimeError("No se han seleccionado vídeos.")

        print("Cargando modelos OpenVINO...")
        model_paths = build_model_paths(args.models_dir)
        check_models(model_paths)

        core = ov.Core()
        models = {
            name: core.compile_model(path, "CPU")
            for name, path in model_paths.items()
        }

        gaze_jumps = []

        for index, video in enumerate(selected_videos, 1):
            print(
                f"Procesando vídeo {index} de {len(selected_videos)}: "
                f"{parse_participant(video)} - {video.name}"
            )
            gaze_jumps.extend(process_video(video, models, args))

        if not gaze_jumps:
            raise RuntimeError(
                "La ejecución no produjo saltos angulares válidos. "
                "No se han guardado resultados."
            )

        save_results(gaze_jumps)
        print("Prueba terminada. Resultados guardados en el CSV.")

    except KeyboardInterrupt:
        print("Prueba cancelada. No se han guardado resultados.")
    except Exception as error:
        print(f"Error: {error}")
        print("No se han guardado resultados.")


if __name__ == "__main__":
    main()