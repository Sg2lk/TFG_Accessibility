import argparse
import math
import random
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

import cv2
import numpy as np
import openvino as ov


DEFAULT_DATASET_ROOT = r"C:\Users\alexa\OneDrive\Documents\TFG\DataSet\EOTT\WebGazerETRA2018Dataset_Release20180420"
DEFAULT_MODELS_DIR = "openvino_models/intel"
VIDEO_EXTENSIONS = {".webm", ".mp4"}


def build_model_paths(models_dir: Path):
    return {
        "face": models_dir / "face-detection-adas-0001/FP32/face-detection-adas-0001.xml",
        "landmarks": models_dir / "facial-landmarks-35-adas-0002/FP32/facial-landmarks-35-adas-0002.xml",
        "headpose": models_dir / "head-pose-estimation-adas-0001/FP32/head-pose-estimation-adas-0001.xml",
        "gaze": models_dir / "gaze-estimation-adas-0002/FP32/gaze-estimation-adas-0002.xml",
    }


def check_models(model_paths):
    missing = [str(path) for path in model_paths.values() if not path.exists()]
    if missing:
        print("Faltan modelos OpenVINO:")
        for path in missing:
            print(" -", path)
        raise SystemExit("Descarga los modelos o corrige --models-dir.")


def parse_participant(path: Path):
    for part in path.parts:
        if part.upper().startswith("P_"):
            return part
    return path.parent.name


def collect_videos(root: Path, extensions):
    if not root.exists():
        raise SystemExit(f"No existe la ruta del dataset: {root}")
    extensions = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions}
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in extensions)


def select_balanced_videos(video_paths, videos_per_participant, max_participants, max_videos, seed):
    rng = random.Random(seed) if seed is not None else random.Random()
    groups = defaultdict(list)
    for path in video_paths:
        groups[parse_participant(path)].append(path)

    participants = sorted(groups.keys())
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
    _, c, h, w = list(input_tensor.shape)
    resized = cv2.resize(frame, (w, h))
    blob = resized.transpose(2, 0, 1) if c == 3 else resized
    return np.expand_dims(blob, axis=0).astype(np.float32)


def first_output(result):
    return next(iter(result.values()))


def timed_infer_single_input(compiled_model, frame):
    t0 = time.perf_counter()
    result = compiled_model([preprocess(frame, compiled_model.inputs[0])])
    return result, (time.perf_counter() - t0) * 1000


def clamp_box(x1, y1, x2, y2, w, h):
    x1 = max(0, min(w - 1, int(x1)))
    y1 = max(0, min(h - 1, int(y1)))
    x2 = max(0, min(w - 1, int(x2)))
    y2 = max(0, min(h - 1, int(y2)))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def crop_box(frame, box):
    x1, y1, x2, y2 = box
    return frame[y1:y2, x1:x2].copy()


def get_face_bbox(face_result, frame_w, frame_h, conf_threshold):
    detections = first_output(face_result)[0][0]
    best = None
    best_conf = 0.0
    for det in detections:
        conf = float(det[2])
        if conf < conf_threshold:
            continue
        box = clamp_box(det[3] * frame_w, det[4] * frame_h, det[5] * frame_w, det[6] * frame_h, frame_w, frame_h)
        if box is not None and conf > best_conf:
            best = box
            best_conf = conf
    return best, best_conf


def get_landmarks(landmarks_result, face_box):
    output = first_output(landmarks_result).reshape(-1)
    x1, y1, x2, y2 = face_box
    fw = x2 - x1
    fh = y2 - y1
    return [(x1 + int(output[i] * fw), y1 + int(output[i + 1] * fh)) for i in range(0, len(output), 2)]


def square_eye_crop(frame, p_a, p_b, scale=2.2):
    h, w = frame.shape[:2]
    cx = int((p_a[0] + p_b[0]) / 2)
    cy = int((p_a[1] + p_b[1]) / 2)
    eye_width = float(np.hypot(p_a[0] - p_b[0], p_a[1] - p_b[1]))
    size = int(max(28, eye_width * scale))
    box = clamp_box(cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2, w, h)
    if box is None:
        return None
    crop = crop_box(frame, box)
    return crop if crop.size else None


def get_head_pose(headpose_result):
    values = {output.get_any_name(): float(value.reshape(-1)[0]) for output, value in headpose_result.items()}
    yaw = values.get("angle_y_fc", values.get("fc_y", 0.0))
    pitch = values.get("angle_p_fc", values.get("fc_p", 0.0))
    roll = values.get("angle_r_fc", values.get("fc_r", 0.0))
    return np.array([[yaw, pitch, roll]], dtype=np.float32), yaw, pitch, roll


def angular_distance_deg(v1, v2):
    a = np.asarray(v1, dtype=np.float64)
    b = np.asarray(v2, dtype=np.float64)
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return None
    cosang = float(np.dot(a, b) / (na * nb))
    cosang = max(-1.0, min(1.0, cosang))
    return math.degrees(math.acos(cosang))


def image_quality(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray)), float(cv2.Laplacian(gray, cv2.CV_64F).var())


def safe_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def percentile(values, p):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return 0.0
    if len(vals) == 1:
        return float(vals[0])
    idx = (len(vals) - 1) * (p / 100.0)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(vals[lo])
    return float(vals[lo] + (vals[hi] - vals[lo]) * (idx - lo))


def longest_failure_run(rows):
    longest = 0
    current = 0
    for row in rows:
        if row.get("ok"):
            longest = max(longest, current)
            current = 0
        else:
            current += 1
    return max(longest, current)


def summarize_values(label, values, suffix=""):
    values = [v for v in values if v is not None]
    if not values:
        print(f"{label}: no disponible")
        return
    print(
        f"{label}: media {mean(values):.2f}{suffix} | "
        f"mediana {median(values):.2f}{suffix} | "
        f"p95 {percentile(values, 95):.2f}{suffix} | "
        f"p99 {percentile(values, 99):.2f}{suffix}"
    )


def process_frame(frame, models, face_conf):
    h, w = frame.shape[:2]
    brightness, blur = image_quality(frame)
    total_t0 = time.perf_counter()
    timings = {"face_ms": None, "landmarks_ms": None, "headpose_ms": None, "gaze_ms": None, "eye_crop_ms": None}

    try:

        face_result, timings["face_ms"] = timed_infer_single_input(models["face"], frame)
        face_box, face_score = get_face_bbox(face_result, w, h, face_conf)
        if face_box is None:
            return {
                "ok": False,
                "failure_reason": "face_not_detected",
                "width": w,
                "height": h,
                "brightness": brightness,
                "blur_laplacian": blur,
                "face_conf": face_score,
                **timings,
                "total_ms": (time.perf_counter() - total_t0) * 1000,
            }

        face_crop = crop_box(frame, face_box)


        landmarks_result, timings["landmarks_ms"] = timed_infer_single_input(models["landmarks"], face_crop)
        landmarks = get_landmarks(landmarks_result, face_box)


        headpose_result, timings["headpose_ms"] = timed_infer_single_input(models["headpose"], face_crop)
        head_angles, head_yaw, head_pitch, head_roll = get_head_pose(headpose_result)


        eye_t0 = time.perf_counter()
        left_eye = square_eye_crop(frame, landmarks[0], landmarks[1])
        right_eye = square_eye_crop(frame, landmarks[2], landmarks[3])
        timings["eye_crop_ms"] = (time.perf_counter() - eye_t0) * 1000
        if left_eye is None or right_eye is None:
            return {
                "ok": False,
                "failure_reason": "eye_crop_failed",
                "width": w,
                "height": h,
                "brightness": brightness,
                "blur_laplacian": blur,
                "face_conf": face_score,
                "head_yaw": head_yaw,
                "head_pitch": head_pitch,
                "head_roll": head_roll,
                **timings,
                "total_ms": (time.perf_counter() - total_t0) * 1000,
            }


        gaze_t0 = time.perf_counter()
        gaze_result = models["gaze"]({
            "left_eye_image": preprocess(left_eye, models["gaze"].input("left_eye_image")),
            "right_eye_image": preprocess(right_eye, models["gaze"].input("right_eye_image")),
            "head_pose_angles": head_angles,
        })
        timings["gaze_ms"] = (time.perf_counter() - gaze_t0) * 1000
        gaze_vector = first_output(gaze_result).reshape(-1)

        return {
            "ok": True,
            "failure_reason": "",
            "width": w,
            "height": h,
            "brightness": brightness,
            "blur_laplacian": blur,
            "face_conf": face_score,
            "head_yaw": head_yaw,
            "head_pitch": head_pitch,
            "head_roll": head_roll,
            "gaze_x": float(gaze_vector[0]),
            "gaze_y": float(gaze_vector[1]),
            "gaze_z": float(gaze_vector[2]),
            "gaze_norm": float(np.linalg.norm(gaze_vector)),
            **timings,
            "total_ms": (time.perf_counter() - total_t0) * 1000,
        }
    except Exception as exc:
        return {
            "ok": False,
            "failure_reason": f"exception:{type(exc).__name__}",
            "width": w,
            "height": h,
            "brightness": brightness,
            "blur_laplacian": blur,
            **timings,
            "total_ms": (time.perf_counter() - total_t0) * 1000,
        }


def process_video(video_path, models, args):
    participant = parse_participant(video_path)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "participant": participant,
            "video_name": video_path.name,
            "path": str(video_path),
            "fps": 0.0,
            "rows": [],
            "sampled": 0,
            "ok": 0,
            "success_rate": 0.0,
            "failures": {"video_open_error": 1},
            "longest_failure_run": 0,
        }

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_idx = 0
    sampled = 0
    ok_count = 0
    failures = defaultdict(int)
    rows = []
    prev_gaze = None
    prev_head = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx < args.skip_initial_frames:
            frame_idx += 1
            continue

        if frame_idx % args.frame_step == 0:
            result = process_frame(frame, models, args.face_conf)
            sampled += 1


            gaze_jump_deg = None
            head_jump_deg = None
            if result.get("ok"):
                ok_count += 1
                current_gaze = np.array([result["gaze_x"], result["gaze_y"], result["gaze_z"]], dtype=np.float64)
                current_head = np.array([result["head_yaw"], result["head_pitch"], result["head_roll"]], dtype=np.float64)
                if prev_gaze is not None:
                    gaze_jump_deg = angular_distance_deg(prev_gaze, current_gaze)
                if prev_head is not None:
                    head_jump_deg = float(np.linalg.norm(current_head - prev_head))
                prev_gaze = current_gaze
                prev_head = current_head
            else:
                failures[result.get("failure_reason", "unknown")] += 1
                prev_gaze = None
                prev_head = None

            result.update({
                "participant": participant,
                "video_name": video_path.name,
                "path": str(video_path),
                "frame_idx": frame_idx,
                "timestamp_ms": cap.get(cv2.CAP_PROP_POS_MSEC),
                "gaze_jump_deg": gaze_jump_deg,
                "head_pose_jump_deg": head_jump_deg,
            })
            rows.append(result)

            if args.max_frames_per_video and sampled >= args.max_frames_per_video:
                break

        frame_idx += 1

    cap.release()
    return {
        "participant": participant,
        "video_name": video_path.name,
        "path": str(video_path),
        "fps": fps,
        "rows": rows,
        "sampled": sampled,
        "ok": ok_count,
        "success_rate": (ok_count / sampled * 100.0) if sampled else 0.0,
        "failures": dict(failures),
        "longest_failure_run": longest_failure_run(rows),
    }


def print_problem_videos(video_summaries, top_n):
    problematic = []
    for item in video_summaries:
        fail_count = item["sampled"] - item["ok"]
        if fail_count > 0 or item["success_rate"] < 100.0 or item["longest_failure_run"] > 0:
            problematic.append((item["success_rate"], fail_count, item["longest_failure_run"], item))

    problematic.sort(key=lambda x: (x[0], -x[1], -x[2]))
    if not problematic:
        print("\nVídeos problemáticos: ninguno. Todos los vídeos seleccionados tuvieron 100% de pipeline completo válido.")
        return

    print(f"\nVídeos problemáticos o con bajada de métricas (top {min(top_n, len(problematic))}):")
    for success_rate, fail_count, longest, item in problematic[:top_n]:
        print("-" * 80)
        print(f"Participante: {item['participant']} | vídeo: {item['video_name']}")
        print(f"Ruta: {item['path']}")
        print(f"Éxito: {success_rate:.1f}% | fallos: {fail_count}/{item['sampled']} | racha máx: {longest}")
        if item["failures"]:
            print("Motivos de fallo:")
            for reason, count in sorted(item["failures"].items(), key=lambda x: x[1], reverse=True):
                print(f"  - {reason}: {count}")


def print_summary(video_summaries):
    all_rows = [row for item in video_summaries for row in item["rows"]]
    ok_rows = [r for r in all_rows if r.get("ok")]
    fail_rows = [r for r in all_rows if not r.get("ok")]

    print("\n" + "=" * 80)
    print("RESUMEN OPENVINO / EOTT - MÉTRICAS COMUNES")
    print("=" * 80)


    total = len(all_rows)
    print("\n[MÉTRICA 1] Disponibilidad de señal / pipeline completo")
    print(f"Frames muestreados: {total}")
    print(f"Frames válidos completos: {len(ok_rows)} ({(len(ok_rows) / total * 100) if total else 0:.1f}%)")
    print(f"Frames con fallo: {len(fail_rows)} ({(len(fail_rows) / total * 100) if total else 0:.1f}%)")

    failures = defaultdict(int)
    for row in fail_rows:
        failures[row.get("failure_reason", "unknown")] += 1
    if failures:
        print("Fallos por fase:")
        for reason, count in sorted(failures.items(), key=lambda x: x[1], reverse=True):
            print(f" - {reason}: {count}")


    print("\n[MÉTRICA 2] Racha máxima de fallos")
    print(f"Racha máxima global: {longest_failure_run(all_rows)} frames muestreados")


    print("\n[MÉTRICA 3] Latencia")
    summarize_values("Tiempo total por frame", [safe_float(r.get("total_ms")) for r in all_rows], " ms")
    summarize_values("Face detection", [safe_float(r.get("face_ms")) for r in all_rows], " ms")
    summarize_values("Facial landmarks", [safe_float(r.get("landmarks_ms")) for r in ok_rows], " ms")
    summarize_values("Head pose", [safe_float(r.get("headpose_ms")) for r in ok_rows], " ms")
    summarize_values("Eye crop", [safe_float(r.get("eye_crop_ms")) for r in ok_rows], " ms")
    summarize_values("Gaze estimation", [safe_float(r.get("gaze_ms")) for r in ok_rows], " ms")


    print("\n[MÉTRICA 4] Estabilidad temporal nativa")
    gaze_jumps = [safe_float(r.get("gaze_jump_deg")) for r in ok_rows]
    head_jumps = [safe_float(r.get("head_pose_jump_deg")) for r in ok_rows]
    summarize_values("Salto angular gaze_vector frame a frame", gaze_jumps, " grados")
    summarize_values("Salto de head pose frame a frame", head_jumps, " grados")
    gaze_jumps_clean = [v for v in gaze_jumps if v is not None]
    if gaze_jumps_clean:
        print(
            "Saltos gaze_vector > 5º: "
            f"{sum(v > 5 for v in gaze_jumps_clean)} | > 10º: {sum(v > 10 for v in gaze_jumps_clean)} | > 15º: {sum(v > 15 for v in gaze_jumps_clean)}"
        )


    print("\n[MÉTRICA 5] Calidad visual contextual")
    summarize_values("Brillo medio", [safe_float(r.get("brightness")) for r in all_rows])
    summarize_values("Confianza facial", [safe_float(r.get("face_conf")) for r in all_rows])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default=DEFAULT_DATASET_ROOT)
    parser.add_argument("--models-dir", default=DEFAULT_MODELS_DIR)
    parser.add_argument("--videos-per-participant", type=int, default=2)
    parser.add_argument("--max-participants", type=int, default=6)
    parser.add_argument("--max-videos", type=int, default=0)
    parser.add_argument("--frame-step", type=int, default=1, help="Para estabilidad temporal conviene 1. Usa 5/10 si tarda demasiado.")
    parser.add_argument("--max-frames-per-video", type=int, default=300)
    parser.add_argument("--skip-initial-frames", type=int, default=30)
    parser.add_argument("--face-conf", type=float, default=0.45)
    parser.add_argument("--extensions", nargs="+", default=[".webm", ".mp4"])
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--top-problem-videos", type=int, default=10)
    args = parser.parse_args()

    if args.frame_step < 1:
        raise SystemExit("--frame-step debe ser >= 1")

    all_videos = collect_videos(Path(args.dataset_root), args.extensions)
    selected = select_balanced_videos(all_videos, args.videos_per_participant, args.max_participants, args.max_videos, args.seed)
    if not selected:
        raise SystemExit("No se han seleccionado vídeos.")

    print(f"Vídeos encontrados: {len(all_videos)}")
    print(f"Vídeos seleccionados: {len(selected)}")
    print(f"Seed: {args.seed if args.seed is not None else 'aleatoria'}")

    model_paths = build_model_paths(Path(args.models_dir))
    check_models(model_paths)
    core = ov.Core()
    models = {name: core.compile_model(path, "CPU") for name, path in model_paths.items()}

    summaries = []
    for idx, video in enumerate(selected, 1):
        print(f"[{idx}/{len(selected)}] {parse_participant(video)} - {video.name}")
        summaries.append(process_video(video, models, args))

    print_summary(summaries)
    print_problem_videos(summaries, args.top_problem_videos)


if __name__ == "__main__":
    main()