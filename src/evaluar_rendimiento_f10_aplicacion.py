import argparse
import os
import sys
import time
from pathlib import Path


current_file = Path(__file__).resolve()
current_dir = current_file.parent

if current_dir.name == "src":
    project_root = current_dir.parent
else:
    project_root = current_dir

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


try:
    import psutil
except ImportError:
    psutil = None


from src.app import Application
from src.app_logging import setup_logging
from src.platforms.factory import get_platform


class SimpleStats:


    def __init__(self):
        self.values = []

    def add(self, value):
        self.values.append(value)

    def count(self):
        return len(self.values)

    def mean(self):
        if not self.values:
            return None
        return sum(self.values) / len(self.values)

    def median(self):
        return self.percentile(50)

    def percentile(self, percent):
        if not self.values:
            return None

        ordered = sorted(self.values)
        index = int(round((percent / 100) * (len(ordered) - 1)))
        return ordered[index]

    def maximum(self):
        if not self.values:
            return None
        return max(self.values)

    def minimum(self):
        if not self.values:
            return None
        return min(self.values)


class PerformanceApplication(Application):


    def __init__(self, duration, warmup):
        super().__init__()

        self.duration = duration
        self.warmup = warmup

        self.loop_start_time = None
        self.measurement_started = False
        self.measurement_finished = False

        self.frames = 0
        self.camera_failures = 0
        self.faces_detected = 0
        self.faces_not_detected = 0

        self.capture_times = SimpleStats()
        self.tracking_times = SimpleStats()
        self.cursor_times = SimpleStats()
        self.cycle_times = SimpleStats()
        self.frame_intervals = SimpleStats()

        self.last_frame_end_time = None

        self.cpu_samples = SimpleStats()
        self.ram_samples_mb = SimpleStats()
        self.last_resource_sample_time = 0
        self.process = None

        if psutil is not None:
            self.process = psutil.Process(os.getpid())

            self.process.cpu_percent(interval=None)

    def _is_measuring_now(self):
        if self.loop_start_time is None:
            return False

        elapsed = time.perf_counter() - self.loop_start_time
        return elapsed >= self.warmup

    def _should_finish_test(self):
        if self.loop_start_time is None:
            return False

        elapsed = time.perf_counter() - self.loop_start_time
        return elapsed >= self.warmup + self.duration

    def _sample_resources(self):
        if self.process is None:
            return

        now = time.perf_counter()
        if now - self.last_resource_sample_time < 1.0:
            return

        self.last_resource_sample_time = now

        cpu = self.process.cpu_percent(interval=None)
        ram_mb = self.process.memory_info().rss / (1024 * 1024)

        self.cpu_samples.add(cpu)
        self.ram_samples_mb.add(ram_mb)

    def _process_cursor(self, face_data):
        start = time.perf_counter()
        super()._process_cursor(face_data)
        end = time.perf_counter()

        if self._is_measuring_now():
            self.cursor_times.add((end - start) * 1000)

    def _run_active_loop(self):
        self._refresh_screen_metrics()

        print("\nMedición iniciada.")
        print("Primero se descartan %.1f s de calentamiento." % self.warmup)
        print("Después se miden %.1f s de ejecución real.\n" % self.duration)

        self.loop_start_time = time.perf_counter()

        while self.running:
            if self._should_finish_test():
                self.running = False
                self.measurement_finished = True
                break

            cycle_start = time.perf_counter()
            measuring = self._is_measuring_now()

            if measuring and not self.measurement_started:
                self.measurement_started = True
                print("Midiendo rendimiento... no cierres la aplicación.\n")


            capture_start = time.perf_counter()
            frame = self.camera.read_frame()
            capture_end = time.perf_counter()

            if measuring:
                self.capture_times.add((capture_end - capture_start) * 1000)

            if frame is None:
                if measuring:
                    self.frames += 1
                    self.camera_failures += 1
                time.sleep(0.001)
                continue


            tracking_start = time.perf_counter()
            face_data = self.tracker.detect(frame)
            tracking_end = time.perf_counter()

            if measuring:
                self.frames += 1
                self.tracking_times.add((tracking_end - tracking_start) * 1000)

                if face_data and face_data.get("face_detected"):
                    self.faces_detected += 1
                else:
                    self.faces_not_detected += 1


            self.keyboard_overlay.poll_events(self.dwell)
            self._handle_face_safety(face_data)

            self.latest_gesture_data = self._process_gestures(face_data)
            gesture_event = self.gesture_controller.update(self.latest_gesture_data)

            previous_state = self.interaction.state
            self.interaction.update(dwell_event=None, gesture_event=gesture_event)

            if self.interaction.state != previous_state:
                self.dwell.reset()
                self.selected_command_option = None
                self._handle_state_transition(previous_state, self.interaction.state)

            self._process_state_logic(face_data)

            self.command_overlay.update_for_state(
                state=self.interaction.state,
                selected_option=self.selected_command_option,
                dwell_progress=self.dwell.progress,
                target_x=self.command_target_x,
                target_y=self.command_target_y,
            )


            cycle_end = time.perf_counter()

            if measuring:
                self.cycle_times.add((cycle_end - cycle_start) * 1000)

                if self.last_frame_end_time is not None:
                    interval = cycle_end - self.last_frame_end_time
                    self.frame_intervals.add(interval)

                self.last_frame_end_time = cycle_end
                self._sample_resources()

            time.sleep(0.001)

    def print_results(self):
        print("\n" + "=" * 76)
        print("RESULTADOS DE RENDIMIENTO GENERAL DE LA APLICACIÓN - F10")
        print("=" * 76)

        print("Duración medida:                    %.2f s" % self.duration)
        print("Warmup configurado:                 %.2f s" % self.warmup)
        print("Frames procesados:                  %d" % self.frames)
        print("Frames sin imagen de cámara:        %d" % self.camera_failures)
        print("Frames con rostro detectado:        %d" % self.faces_detected)
        print("Frames sin rostro detectado:        %d" % self.faces_not_detected)

        if self.frames > 0:
            face_rate = (self.faces_detected / self.frames) * 100
            fps_global = self.frames / self.duration
            print("Tasa de rostro detectado:           %.2f %%" % face_rate)
        else:
            fps_global = 0
            print("Tasa de rostro detectado:           N/D")

        print("\n1) FPS")
        print("   FPS medio global:                %.2f" % fps_global)

        if self.frame_intervals.count() > 0:
            fps_values = SimpleStats()
            for interval in self.frame_intervals.values:
                if interval > 0:
                    fps_values.add(1.0 / interval)

            print("   FPS mínimo instantáneo:          %s" % format_number(fps_values.minimum()))
            print("   FPS p5 instantáneo:              %s" % format_number(fps_values.percentile(5)))
            print("   FPS mediana instantánea:         %s" % format_number(fps_values.median()))
            print("   FPS p95 instantáneo:             %s" % format_number(fps_values.percentile(95)))
        else:
            print("   FPS instantáneo:                 N/D")

        print("\n2) Tiempo por frame/ciclo")
        print_stats_ms("   Tiempo de ciclo procesado", self.cycle_times)

        print("\n3) Uso de CPU del proceso")
        if self.cpu_samples.count() > 0:
            print("   CPU media:                       %.2f %%" % self.cpu_samples.mean())
            print("   CPU p95:                         %.2f %%" % self.cpu_samples.percentile(95))
            print("   CPU máxima:                      %.2f %%" % self.cpu_samples.maximum())
        else:
            print("   N/D. Instala psutil para medir CPU: pip install psutil")

        print("\n4) Uso de RAM del proceso")
        if self.ram_samples_mb.count() > 0:
            print("   RAM media:                       %.2f MB" % self.ram_samples_mb.mean())
            print("   RAM p95:                         %.2f MB" % self.ram_samples_mb.percentile(95))
            print("   RAM máxima:                      %.2f MB" % self.ram_samples_mb.maximum())
        else:
            print("   N/D. Instala psutil para medir RAM: pip install psutil")

        print("\n5) Desglose auxiliar por etapa")
        print_stats_ms("   Captura de cámara", self.capture_times)
        print_stats_ms("   Seguimiento facial / MediaPipe", self.tracking_times)
        print_stats_ms("   Procesamiento del cursor", self.cursor_times)

        if self.cursor_times.count() == 0:
            print("   Nota: no se registró procesamiento del cursor.")
            print("   Esto puede ocurrir si la aplicación permaneció en pausa durante la prueba.")

        print("=" * 76)


def format_number(value):
    if value is None:
        return "N/D"
    return "%.2f" % value


def print_stats_ms(title, stats):
    if stats.count() == 0:
        print(title)
        print("      N/D")
        return

    print(title)
    print("      Media:                        %.2f ms" % stats.mean())
    print("      Mediana:                      %.2f ms" % stats.median())
    print("      p95:                          %.2f ms" % stats.percentile(95))
    print("      Máximo:                       %.2f ms" % stats.maximum())


def read_arguments():
    parser = argparse.ArgumentParser(
        description="Evalúa métricas simples de rendimiento del prototipo."
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Segundos medidos después del warmup. Por defecto: 60."
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=3.0,
        help="Segundos iniciales descartados. Por defecto: 3."
    )
    return parser.parse_args()


def main():
    args = read_arguments()

    platform = get_platform()
    platform.enable_dpi_awareness()

    setup_logging()

    app = PerformanceApplication(
        duration=args.duration,
        warmup=args.warmup,
    )

    try:
        app.run()
    finally:
        app.print_results()


if __name__ == "__main__":
    main()
