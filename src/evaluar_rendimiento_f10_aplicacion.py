import argparse
import csv
import math
import sys
import time
from pathlib import Path


ARCHIVO_ACTUAL = Path(__file__).resolve()
CARPETA_ACTUAL = ARCHIVO_ACTUAL.parent
RESULTADOS_CSV = CARPETA_ACTUAL / "rendimiento.csv"
RAIZ_PROYECTO = CARPETA_ACTUAL.parent if CARPETA_ACTUAL.name == "src" else CARPETA_ACTUAL

if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from src.app import Application
from src.app_logging import setup_logging
from src.platforms.factory import get_platform


CABECERA_CSV = [
    "Ejecución",
    "Frames totales evaluados",
    "FPS medios",
    "FPS pico máximo",
    "FPS p95",
    "FPS p99",
    "Frames descartados",
    "Jitter (ms)",
    "Captura media cámara (ms)",
    "Seguimiento facial medio (ms)",
    "Duración prueba (s)",
    "Procesamiento medio cursor (ms)",
]

CABECERA_ANTERIOR = CABECERA_CSV[1:]


class Estadisticas:
    def __init__(self):
        self.valores = []

    def añadir(self, valor):
        self.valores.append(valor)

    def media(self):
        return sum(self.valores) / len(self.valores) if self.valores else None

    def percentil(self, porcentaje):
        if not self.valores:
            return None

        ordenados = sorted(self.valores)
        posicion = round((porcentaje / 100) * (len(ordenados) - 1))
        return ordenados[posicion]

    def maximo(self):
        return max(self.valores) if self.valores else None

    def desviacion_estandar(self):
        if not self.valores:
            return None

        valor_medio = self.media()
        varianza = sum((valor - valor_medio) ** 2 for valor in self.valores)
        return math.sqrt(varianza / len(self.valores))


class AplicacionRendimiento(Application):
    def __init__(self, duracion, calentamiento):
        super().__init__()

        self.duracion = duracion
        self.calentamiento = calentamiento
        self.inicio_bucle = None
        self.medicion_finalizada = False

        self.frames_validos = 0
        self.frames_descartados = 0
        self.tiempos_captura = Estadisticas()
        self.tiempos_seguimiento = Estadisticas()
        self.tiempos_cursor = Estadisticas()
        self.intervalos_frames = Estadisticas()
        self.ultimo_fin_frame = None

    def _midiendo(self):
        if self.inicio_bucle is None:
            return False

        return time.perf_counter() - self.inicio_bucle >= self.calentamiento

    def _prueba_finalizada(self):
        if self.inicio_bucle is None:
            return False

        return time.perf_counter() - self.inicio_bucle >= self.calentamiento + self.duracion

    def _process_cursor(self, face_data):
        inicio = time.perf_counter()
        super()._process_cursor(face_data)
        fin = time.perf_counter()

        if self._midiendo():
            self.tiempos_cursor.añadir((fin - inicio) * 1000)

    def _run_active_loop(self):
        self._refresh_screen_metrics()
        self.inicio_bucle = time.perf_counter()
        print(
            f"Prueba iniciada: {self.calentamiento:.0f} s de calentamiento "
            f"y {self.duracion:.0f} s de medición."
        )

        while self.running:
            if self._prueba_finalizada():
                self.running = False
                self.medicion_finalizada = True
                break

            midiendo = self._midiendo()

            inicio_captura = time.perf_counter()
            frame = self.camera.read_frame()
            fin_captura = time.perf_counter()

            if midiendo:
                self.tiempos_captura.añadir((fin_captura - inicio_captura) * 1000)

            if frame is None:
                if midiendo:
                    self.frames_descartados += 1

                time.sleep(0.001)
                continue

            inicio_seguimiento = time.perf_counter()
            face_data = self.tracker.detect(frame)
            fin_seguimiento = time.perf_counter()

            if midiendo:
                self.frames_validos += 1
                self.tiempos_seguimiento.añadir(
                    (fin_seguimiento - inicio_seguimiento) * 1000
                )

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

            if midiendo:
                fin_frame = time.perf_counter()

                if self.ultimo_fin_frame is not None:
                    self.intervalos_frames.añadir(fin_frame - self.ultimo_fin_frame)

                self.ultimo_fin_frame = fin_frame

            time.sleep(0.001)


def numero_csv(valor):
    return "" if valor is None else f"{valor:.2f}".replace(".", ",")


def preparar_csv_existente():
    if not RESULTADOS_CSV.exists() or RESULTADOS_CSV.stat().st_size == 0:
        return

    with RESULTADOS_CSV.open("r", newline="", encoding="utf-8-sig") as archivo:
        filas = list(csv.reader(archivo, delimiter=";"))

    if not filas or filas[0] == CABECERA_CSV:
        return

    if filas[0] != CABECERA_ANTERIOR:
        raise RuntimeError(
            "El CSV existente no tiene un formato compatible. "
            "Renómbralo o elimínalo antes de continuar."
        )

    filas_actualizadas = [CABECERA_CSV]

    for ejecucion, fila in enumerate(filas[1:], 1):
        if any(celda.strip() for celda in fila):
            filas_actualizadas.append([ejecucion, *fila])

    with RESULTADOS_CSV.open("w", newline="", encoding="utf-8-sig") as archivo:
        csv.writer(archivo, delimiter=";").writerows(filas_actualizadas)


def obtener_numero_ejecucion():
    preparar_csv_existente()

    if not RESULTADOS_CSV.exists() or RESULTADOS_CSV.stat().st_size == 0:
        return 1

    ejecuciones = []

    with RESULTADOS_CSV.open("r", newline="", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")

        for fila in lector:
            try:
                ejecuciones.append(int((fila.get("Ejecución") or "").strip()))
            except ValueError:
                continue

    return max(ejecuciones, default=0) + 1


def calcular_fps(intervalos):
    valores_fps = Estadisticas()

    for intervalo in intervalos.valores:
        if intervalo > 0:
            valores_fps.añadir(1 / intervalo)

    return valores_fps


def guardar_resultados(app):
    preparar_csv_existente()
    archivo_existente = RESULTADOS_CSV.exists() and RESULTADOS_CSV.stat().st_size > 0
    ejecucion = obtener_numero_ejecucion()
    fps_global = app.frames_validos / app.duracion if app.duracion > 0 else 0.0
    valores_fps = calcular_fps(app.intervalos_frames)
    intervalos_ms = Estadisticas()

    for intervalo in app.intervalos_frames.valores:
        intervalos_ms.añadir(intervalo * 1000)

    fila = [
        ejecucion,
        app.frames_validos + app.frames_descartados,
        numero_csv(fps_global),
        numero_csv(valores_fps.maximo()),
        numero_csv(valores_fps.percentil(95)),
        numero_csv(valores_fps.percentil(99)),
        app.frames_descartados,
        numero_csv(intervalos_ms.desviacion_estandar()),
        numero_csv(app.tiempos_captura.media()),
        numero_csv(app.tiempos_seguimiento.media()),
        numero_csv(app.duracion),
        numero_csv(app.tiempos_cursor.media()),
    ]

    with RESULTADOS_CSV.open("a", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")

        if not archivo_existente:
            escritor.writerow(CABECERA_CSV)

        escritor.writerow(fila)


def leer_argumentos():
    parser = argparse.ArgumentParser(
        description="Evalúa el rendimiento general del prototipo."
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=60.0,
        help="Segundos de medición después del calentamiento. Por defecto: 30.",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=3.0,
        help="Segundos iniciales descartados. Por defecto: 3.",
    )
    return parser.parse_args()


def main():
    argumentos = leer_argumentos()

    platform = get_platform()
    platform.enable_dpi_awareness()

    setup_logging()

    app = AplicacionRendimiento(
        duracion=argumentos.duration,
        calentamiento=argumentos.warmup,
    )

    try:
        app.run()
    except KeyboardInterrupt:
        print("Prueba cancelada. No se han guardado resultados.")
        return
    except Exception as error:
        print(f"Error: {error}")
        return

    if app.medicion_finalizada:
        guardar_resultados(app)
        print("Prueba terminada. Resultados guardados en el CSV.")
    else:
        print("Prueba cancelada. No se han guardado resultados.")


if __name__ == "__main__":
    main()