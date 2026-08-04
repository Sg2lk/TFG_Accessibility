import argparse
import csv
import math
import sys
import time
from pathlib import Path

import cv2
import win32api
import win32con
import win32gui


CAMARA = 0
SEGUNDOS_CALIBRACION = 3.0
VENTANA = "Prueba de latencia movimiento-accion"

CARPETA_ACTUAL = Path(__file__).resolve().parent
RESULTADOS_CSV = CARPETA_ACTUAL / "latencia_cursor.csv"
RAIZ_PROYECTO = CARPETA_ACTUAL.parent if CARPETA_ACTUAL.name == "src" else CARPETA_ACTUAL

if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from src.config import settings
from src.config.user_config import load_and_apply_user_config
from src.processing.cursor import CursorProcessor
from src.processing.precision import PrecisionStabilizer
from src.processing.smoothing import PositionSmoother
from src.vision.camera import Camera
from src.vision.face_tracker import FaceTracker


CABECERA_CSV = [
    "Ejecución",
    "Repetición",
    "Latencia movimiento-acción estimada (ms)",
]

ultimo_timestamp_ms = 0


def obtener_timestamp_ms():
    global ultimo_timestamp_ms

    timestamp_ms = int(time.perf_counter() * 1000)
    ultimo_timestamp_ms = max(timestamp_ms, ultimo_timestamp_ms + 1)
    return ultimo_timestamp_ms


def media(valores):
    return sum(valores) / len(valores) if valores else 0.0


def numero_csv(valor):
    return f"{valor:.2f}".replace(".", ",")


def obtener_numero_ejecucion():
    if not RESULTADOS_CSV.exists() or RESULTADOS_CSV.stat().st_size == 0:
        return 1

    ejecuciones = []

    with RESULTADOS_CSV.open("r", newline="", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")

        if lector.fieldnames != CABECERA_CSV:
            raise RuntimeError(
                "El CSV existente utiliza otro formato. Renómbralo o elimínalo antes de continuar."
            )

        for fila in lector:
            try:
                ejecuciones.append(int((fila.get("Ejecución") or "").strip()))
            except ValueError:
                continue

    return max(ejecuciones, default=0) + 1


def centrar_ventana(nombre):
    cv2.waitKey(1)
    manejador = win32gui.FindWindow(None, nombre)

    if not manejador:
        return

    izquierda, arriba, derecha, abajo = win32gui.GetWindowRect(manejador)
    ancho_ventana = derecha - izquierda
    alto_ventana = abajo - arriba
    ancho_pantalla = win32api.GetSystemMetrics(0)
    alto_pantalla = win32api.GetSystemMetrics(1)
    posicion_x = max(0, (ancho_pantalla - ancho_ventana) // 2)
    posicion_y = max(0, (alto_pantalla - alto_ventana) // 2)

    win32gui.SetWindowPos(
        manejador,
        None,
        posicion_x,
        posicion_y,
        0,
        0,
        win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE,
    )


def preparar_ventana(frame, ancho_pantalla, alto_pantalla):
    alto_frame, ancho_frame = frame.shape[:2]
    proporcion = ancho_frame / max(1, alto_frame)
    ancho_ventana = int(ancho_pantalla * 0.60)
    alto_ventana = int(ancho_ventana / proporcion)
    alto_maximo = int(alto_pantalla * 0.72)

    if alto_ventana > alto_maximo:
        alto_ventana = alto_maximo
        ancho_ventana = int(alto_ventana * proporcion)

    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VENTANA, ancho_ventana, alto_ventana)
    centrar_ventana(VENTANA)


def dibujar_cruz(imagen):
    alto, ancho = imagen.shape[:2]
    centro_x = ancho // 2
    centro_y = alto // 2
    longitud = 35
    color = (255, 255, 255)

    cv2.line(
        imagen,
        (centro_x - longitud, centro_y),
        (centro_x + longitud, centro_y),
        color,
        2,
        cv2.LINE_AA,
    )
    cv2.line(
        imagen,
        (centro_x, centro_y - longitud),
        (centro_x, centro_y + longitud),
        color,
        2,
        cv2.LINE_AA,
    )


class PruebaLatencia:
    def __init__(
        self,
        repeticiones,
        umbral_movimiento,
        umbral_accion,
        desplazamiento_minimo,
        segundos_referencia,
        segundos_validacion,
        tiempo_limite,
    ):
        load_and_apply_user_config(settings)

        self.repeticiones_objetivo = repeticiones
        self.umbral_movimiento = umbral_movimiento
        self.umbral_accion = umbral_accion
        self.desplazamiento_minimo = desplazamiento_minimo
        self.segundos_referencia = segundos_referencia
        self.segundos_validacion = segundos_validacion
        self.tiempo_limite = tiempo_limite

        self.camara = Camera(camera_index=CAMARA)
        self.tracker = FaceTracker()
        self.cursor = CursorProcessor()
        self.smoother = PositionSmoother()
        self.precision = PrecisionStabilizer()
        self.ancho_pantalla, self.alto_pantalla = self.cursor.get_screen_size()

        self.yaw_centro = 0.0
        self.pitch_centro = 0.0
        self.calibrado = False
        self.muestras_calibracion_yaw = []
        self.muestras_calibracion_pitch = []

        self.raw_x = self.ancho_pantalla / 2
        self.raw_y = self.alto_pantalla / 2
        self.pipe_x = self.raw_x
        self.pipe_y = self.raw_y

        self.estado = "sin_calibrar"
        self.inicio_estado = 0.0
        self.origen_raw = None
        self.origen_pipe = None
        self.referencia_raw = []
        self.referencia_pipe = []

        self.movimiento_consecutivo = 0
        self.accion_consecutiva = 0
        self.inicio_movimiento_candidato = None
        self.inicio_accion_candidata = None
        self.inicio_movimiento = None
        self.latencia_pendiente = None
        self.desplazamiento_raw_maximo = 0.0

        self.latencias = []

    def ejecutar(self):
        completada = False

        try:
            print("Iniciando prueba de latencia...")
            self.camara.start()
            self.tracker.start()

            frame_inicial = self._obtener_frame_inicial()
            preparar_ventana(frame_inicial, self.ancho_pantalla, self.alto_pantalla)

            while True:
                inicio_captura = time.perf_counter()
                frame = self.camara.read_frame()

                if frame is None:
                    time.sleep(0.002)
                    continue

                datos_cara = self.tracker.detect(frame, timestamp_ms=obtener_timestamp_ms())
                self._actualizar_calibracion(datos_cara)
                self._actualizar_cursor(datos_cara)
                self._actualizar_prueba_antes_de_enviar(inicio_captura)

                instante_envio = self._mover_cursor_real()
                self._actualizar_prueba_despues_de_enviar(instante_envio)

                cv2.imshow(VENTANA, self._dibujar_estado(frame, datos_cara))
                tecla = cv2.waitKey(1) & 0xFF

                if tecla == 27:
                    break

                if tecla == 32:
                    self._iniciar_calibracion()

                if tecla == 13:
                    self._iniciar_repeticion()

                if len(self.latencias) >= self.repeticiones_objetivo:
                    completada = True
                    break

            if completada:
                self._guardar_csv()
                print("Prueba terminada. Resultados guardados en el CSV.")
            else:
                print("Prueba cancelada. No se han guardado resultados.")

        finally:
            self.tracker.stop()
            self.camara.stop()
            cv2.destroyAllWindows()

    def _obtener_frame_inicial(self):
        limite = time.perf_counter() + 5

        while time.perf_counter() < limite:
            frame = self.camara.read_frame()

            if frame is not None:
                return frame

        raise RuntimeError("No se ha podido obtener una imagen de la cámara.")

    def _cara_valida(self, datos_cara):
        return bool(
            datos_cara
            and datos_cara.get("face_detected")
            and datos_cara.get("yaw") is not None
            and datos_cara.get("pitch") is not None
        )

    def _iniciar_calibracion(self):
        if self.estado not in {"sin_calibrar", "esperando"}:
            return

        self.muestras_calibracion_yaw = []
        self.muestras_calibracion_pitch = []
        self.estado = "calibrando"
        self.inicio_estado = time.perf_counter()

    def _actualizar_calibracion(self, datos_cara):
        if self.estado != "calibrando":
            return

        if self._cara_valida(datos_cara):
            self.muestras_calibracion_yaw.append(float(datos_cara["yaw"]))
            self.muestras_calibracion_pitch.append(float(datos_cara["pitch"]))

        if time.perf_counter() - self.inicio_estado < SEGUNDOS_CALIBRACION:
            return

        if not self.muestras_calibracion_yaw:
            self.estado = "sin_calibrar"
            print("No se ha detectado la cara durante la calibración.")
            return

        self.yaw_centro = media(self.muestras_calibracion_yaw)
        self.pitch_centro = media(self.muestras_calibracion_pitch)
        self.calibrado = True

        centro_x = self.ancho_pantalla / 2
        centro_y = self.alto_pantalla / 2
        self.cursor.reset_to_center()
        self.smoother.reset(centro_x, centro_y)
        self.precision.reset(centro_x, centro_y)
        self.raw_x = centro_x
        self.raw_y = centro_y
        self.pipe_x = centro_x
        self.pipe_y = centro_y
        self.estado = "esperando"

    def _actualizar_cursor(self, datos_cara):
        if not self.calibrado or not self._cara_valida(datos_cara):
            return

        self.raw_x, self.raw_y = self.cursor.update(
            datos_cara["yaw"], datos_cara["pitch"], self.yaw_centro, self.pitch_centro
        )
        smooth_x, smooth_y = self.smoother.update(self.raw_x, self.raw_y)
        self.pipe_x, self.pipe_y = self.precision.update(smooth_x, smooth_y)

    def _iniciar_repeticion(self):
        if not self.calibrado:
            print("Primero debes calibrar con ESPACIO.")
            return

        if self.estado != "esperando":
            return

        self.referencia_raw = []
        self.referencia_pipe = []
        self.origen_raw = None
        self.origen_pipe = None
        self._reiniciar_deteccion()
        self.estado = "referencia"
        self.inicio_estado = time.perf_counter()

    def _reiniciar_deteccion(self):
        self.movimiento_consecutivo = 0
        self.accion_consecutiva = 0
        self.inicio_movimiento_candidato = None
        self.inicio_accion_candidata = None
        self.inicio_movimiento = None
        self.latencia_pendiente = None
        self.desplazamiento_raw_maximo = 0.0

    def _actualizar_prueba_antes_de_enviar(self, inicio_captura):
        if not self.calibrado:
            return

        ahora = time.perf_counter()

        if self.estado == "referencia":
            self.referencia_raw.append((self.raw_x, self.raw_y))
            self.referencia_pipe.append((self.pipe_x, self.pipe_y))

            if ahora - self.inicio_estado >= self.segundos_referencia:
                self.origen_raw = self._punto_medio(self.referencia_raw)
                self.origen_pipe = self._punto_medio(self.referencia_pipe)
                self.estado = "esperando_movimiento"
                self.inicio_estado = ahora

        elif self.estado == "esperando_movimiento":
            distancia_raw = self._distancia_actual_raw()

            if distancia_raw >= self.umbral_movimiento:
                if self.movimiento_consecutivo == 0:
                    self.inicio_movimiento_candidato = inicio_captura

                self.movimiento_consecutivo += 1
            else:
                self.movimiento_consecutivo = 0
                self.inicio_movimiento_candidato = None

            if self.movimiento_consecutivo >= 2:
                self.inicio_movimiento = self.inicio_movimiento_candidato
                self.desplazamiento_raw_maximo = distancia_raw
                self.estado = "esperando_accion"
                self.inicio_estado = ahora
            elif ahora - self.inicio_estado >= self.tiempo_limite:
                self._anular_repeticion("No se detectó un movimiento suficiente.")

        elif self.estado in {"esperando_accion", "validando"}:
            self.desplazamiento_raw_maximo = max(
                self.desplazamiento_raw_maximo, self._distancia_actual_raw()
            )

            if self.estado == "esperando_accion" and ahora - self.inicio_estado >= self.tiempo_limite:
                self._anular_repeticion("No se detectó la acción del cursor dentro del tiempo límite.")

            if self.estado == "validando" and ahora - self.inicio_estado >= self.segundos_validacion:
                self._finalizar_repeticion()

    def _actualizar_prueba_despues_de_enviar(self, instante_envio):
        if self.estado != "esperando_accion":
            return

        distancia_pipe = self._distancia(
            self.pipe_x, self.pipe_y, self.origen_pipe[0], self.origen_pipe[1]
        )

        if distancia_pipe >= self.umbral_accion:
            if self.accion_consecutiva == 0:
                self.inicio_accion_candidata = instante_envio

            self.accion_consecutiva += 1
        else:
            self.accion_consecutiva = 0
            self.inicio_accion_candidata = None

        if self.accion_consecutiva >= 2:
            self.latencia_pendiente = (
                self.inicio_accion_candidata - self.inicio_movimiento
            ) * 1000
            self.estado = "validando"
            self.inicio_estado = time.perf_counter()

    def _finalizar_repeticion(self):
        if self.desplazamiento_raw_maximo < self.desplazamiento_minimo:
            self._anular_repeticion("Repetición anulada: el desplazamiento fue insuficiente.")
            return

        if self.latencia_pendiente is None or self.latencia_pendiente < 0:
            self._anular_repeticion("Repetición anulada: no se pudo estimar la latencia.")
            return

        self.latencias.append(self.latencia_pendiente)
        self.estado = "esperando"
        print(
            f"Repetición válida {len(self.latencias)}/{self.repeticiones_objetivo}. "
            "Vuelve al centro y pulsa ENTER."
        )

    def _anular_repeticion(self, mensaje):
        self.estado = "esperando"
        self._reiniciar_deteccion()
        print(mensaje)

    def _distancia_actual_raw(self):
        return self._distancia(
            self.raw_x, self.raw_y, self.origen_raw[0], self.origen_raw[1]
        )

    def _mover_cursor_real(self):
        if not self.calibrado:
            return time.perf_counter()

        x = max(0, min(round(self.pipe_x), self.ancho_pantalla - 1))
        y = max(0, min(round(self.pipe_y), self.alto_pantalla - 1))
        win32api.SetCursorPos((x, y))
        return time.perf_counter()

    def _dibujar_estado(self, frame, datos_cara):
        imagen = frame.copy()
        rostro_detectado = bool(datos_cara and datos_cara.get("face_detected"))

        if not self.calibrado or self.estado == "calibrando":
            dibujar_cruz(imagen)

        if self.estado == "sin_calibrar":
            estado = "Pulsa ESPACIO para iniciar la calibración"
        elif self.estado == "calibrando":
            restante = max(0.0, SEGUNDOS_CALIBRACION - (time.perf_counter() - self.inicio_estado))
            estado = f"Calibrando: mira a la cruz ({restante:.1f} s)"
        elif self.estado == "referencia":
            estado = "Mantente quieto"
        elif self.estado == "esperando_movimiento":
            estado = "Mueve la cabeza con rapidez y mantén la posición"
        elif self.estado == "esperando_accion":
            estado = "Movimiento detectado: mantén la posición"
        elif self.estado == "validando":
            estado = "Mantén la posición"
        else:
            estado = "Vuelve al centro y pulsa ENTER"

        textos = [
            estado,
            f"Rostro: {'OK' if rostro_detectado else 'NO'}",
            f"Repeticiones: {len(self.latencias)}/{self.repeticiones_objetivo}",
            "ESPACIO: recalibrar",
            "ESC: cancelar",
        ]

        for indice, texto in enumerate(textos):
            cv2.putText(
                imagen,
                texto,
                (20, 30 + indice * 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

        return imagen

    def _guardar_csv(self):
        archivo_existente = RESULTADOS_CSV.exists() and RESULTADOS_CSV.stat().st_size > 0
        ejecucion = obtener_numero_ejecucion()

        with RESULTADOS_CSV.open("a", newline="", encoding="utf-8-sig") as archivo:
            escritor = csv.writer(archivo, delimiter=";")

            if not archivo_existente:
                escritor.writerow(CABECERA_CSV)

            for repeticion, latencia in enumerate(self.latencias, 1):
                escritor.writerow([ejecucion, repeticion, numero_csv(latencia)])

    @staticmethod
    def _distancia(x1, y1, x2, y2):
        return math.hypot(x1 - x2, y1 - y2)

    @staticmethod
    def _punto_medio(puntos):
        return media([punto[0] for punto in puntos]), media([punto[1] for punto in puntos])

def leer_argumentos():
    parser = argparse.ArgumentParser(
        description=(
            "Estima el retardo desde la adquisición del primer fotograma con movimiento "
            "hasta el envío de la acción del cursor pipe al sistema operativo."
        )
    )
    parser.add_argument("--trials", type=int, default=12)
    parser.add_argument("--movement-threshold", type=float, default=12.0)
    parser.add_argument("--action-threshold", type=float, default=12.0)
    parser.add_argument("--min-displacement", type=float, default=40.0)
    parser.add_argument("--baseline-seconds", type=float, default=1.0)
    parser.add_argument("--validation-seconds", type=float, default=0.35)
    parser.add_argument("--timeout", type=float, default=8.0)
    return parser.parse_args()

def main():
    argumentos = leer_argumentos()
    prueba = PruebaLatencia(
        repeticiones=argumentos.trials,
        umbral_movimiento=argumentos.movement_threshold,
        umbral_accion=argumentos.action_threshold,
        desplazamiento_minimo=argumentos.min_displacement,
        segundos_referencia=argumentos.baseline_seconds,
        segundos_validacion=argumentos.validation_seconds,
        tiempo_limite=argumentos.timeout,
    )

    try:
        prueba.ejecutar()
    except Exception as error:
        print(f"Error: {error}")

if __name__ == "__main__":
    main()