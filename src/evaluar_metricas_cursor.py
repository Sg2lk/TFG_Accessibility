import math
import sys
import time
from pathlib import Path


CAMARA = 0
SEGUNDOS_CALIBRACION = 3
SEGUNDOS_CALENTAMIENTO = 1
SEGUNDOS_MEDICION = 15


ruta_actual = Path(__file__).resolve()
carpeta_actual = ruta_actual.parent

if carpeta_actual.name == "src":
    raiz_proyecto = carpeta_actual.parent
else:
    raiz_proyecto = carpeta_actual

if str(raiz_proyecto) not in sys.path:
    sys.path.insert(0, str(raiz_proyecto))


from src.config import settings
from src.config.user_config import load_and_apply_user_config
from src.processing.cursor import CursorProcessor
from src.processing.precision import PrecisionStabilizer
from src.processing.smoothing import PositionSmoother
from src.vision.camera import Camera
from src.vision.face_tracker import FaceTracker


ultimo_timestamp_ms = 0


def obtener_timestamp_ms():
    global ultimo_timestamp_ms

    timestamp_ms = int(time.perf_counter() * 1000)

    if timestamp_ms <= ultimo_timestamp_ms:
        timestamp_ms = ultimo_timestamp_ms + 1

    ultimo_timestamp_ms = timestamp_ms
    return timestamp_ms


def media(valores):
    if len(valores) == 0:
        return 0.0

    return sum(valores) / len(valores)


def mediana(valores):
    if len(valores) == 0:
        return 0.0

    ordenados = sorted(valores)
    centro = len(ordenados) // 2

    if len(ordenados) % 2 == 1:
        return ordenados[centro]

    return (ordenados[centro - 1] + ordenados[centro]) / 2


def percentil_95(valores):
    if len(valores) == 0:
        return 0.0

    ordenados = sorted(valores)
    posicion = int(round(0.95 * (len(ordenados) - 1)))

    return ordenados[posicion]


def desviacion_estandar(valores):
    if len(valores) == 0:
        return 0.0

    valor_medio = media(valores)
    suma = 0.0

    for valor in valores:
        suma += (valor - valor_medio) ** 2

    varianza = suma / len(valores)
    return math.sqrt(varianza)


def crear_medidas_cursor():
    return {
        "x": [],
        "y": [],
        "desplazamientos": [],
        "ultima_posicion": None,
    }


def guardar_posicion(medidas, x, y):
    x = int(x)
    y = int(y)

    if medidas["ultima_posicion"] is not None:
        x_anterior, y_anterior = medidas["ultima_posicion"]
        dx = x - x_anterior
        dy = y - y_anterior
        desplazamiento = math.sqrt(dx * dx + dy * dy)
        medidas["desplazamientos"].append(desplazamiento)

    medidas["x"].append(x)
    medidas["y"].append(y)
    medidas["ultima_posicion"] = (x, y)


def cortar_trayectoria(medidas_raw, medidas_smooth, medidas_pipe):
    medidas_raw["ultima_posicion"] = None
    medidas_smooth["ultima_posicion"] = None
    medidas_pipe["ultima_posicion"] = None


def porcentaje_saltos_mayores_que(desplazamientos, limite):
    if len(desplazamientos) == 0:
        return 0.0

    contador = 0

    for valor in desplazamientos:
        if valor > limite:
            contador += 1

    return contador * 100 / len(desplazamientos)


def imprimir_resultados(nombre, medidas):
    desplazamientos = medidas["desplazamientos"]

    print("\n" + "=" * 60)
    print("Cursor:", nombre)
    print("=" * 60)
    print("Frames válidos:", len(medidas["x"]))
    print("Muestras de desplazamiento:", len(desplazamientos))

    print("Desplazamiento medio entre frames: %.2f px" % media(desplazamientos))
    print("Mediana del desplazamiento:        %.2f px" % mediana(desplazamientos))
    print("p95 del desplazamiento:            %.2f px" % percentil_95(desplazamientos))

    if len(desplazamientos) > 0:
        print("Máximo desplazamiento:             %.2f px" % max(desplazamientos))
    else:
        print("Máximo desplazamiento:             0.00 px")

    print("Desviación estándar X:             %.2f px" % desviacion_estandar(medidas["x"]))
    print("Desviación estándar Y:             %.2f px" % desviacion_estandar(medidas["y"]))
    print("Saltos > 10 px:                    %.2f %%" % porcentaje_saltos_mayores_que(desplazamientos, 10))
    print("Saltos > 30 px:                    %.2f %%" % porcentaje_saltos_mayores_que(desplazamientos, 30))


def leer_datos_cara(camara, tracker):
    frame = camara.read_frame()

    if frame is None:
        return None

    return tracker.detect(frame, timestamp_ms=obtener_timestamp_ms())


def cara_valida(datos_cara):
    if datos_cara is None:
        return False

    if not datos_cara.get("face_detected"):
        return False

    if datos_cara.get("yaw") is None or datos_cara.get("pitch") is None:
        return False

    return True


def calibrar(camara, tracker):
    print("\nCalibración")
    print("Mira al centro durante", SEGUNDOS_CALIBRACION, "segundos.")

    muestras_yaw = []
    muestras_pitch = []
    inicio = time.perf_counter()

    while time.perf_counter() - inicio < SEGUNDOS_CALIBRACION:
        datos_cara = leer_datos_cara(camara, tracker)

        if cara_valida(datos_cara):
            muestras_yaw.append(float(datos_cara.get("yaw")))
            muestras_pitch.append(float(datos_cara.get("pitch")))

    if len(muestras_yaw) == 0:
        raise RuntimeError("No se ha detectado la cara durante la calibración.")

    yaw_centro = media(muestras_yaw)
    pitch_centro = media(muestras_pitch)

    print("Calibración completada con", len(muestras_yaw), "frames válidos.")
    return yaw_centro, pitch_centro


def actualizar_cursores(datos_cara, yaw_centro, pitch_centro, cursor, smoother, precision):
    yaw = datos_cara.get("yaw")
    pitch = datos_cara.get("pitch")

    raw_x, raw_y = cursor.update(yaw, pitch, yaw_centro, pitch_centro)
    smooth_x, smooth_y = smoother.update(raw_x, raw_y)
    pipe_x, pipe_y = precision.update(smooth_x, smooth_y)

    return raw_x, raw_y, smooth_x, smooth_y, pipe_x, pipe_y


def main():
    load_and_apply_user_config(settings)

    camara = Camera(camera_index=CAMARA)
    tracker = FaceTracker()

    cursor = CursorProcessor()
    smoother = PositionSmoother()
    precision = PrecisionStabilizer()

    medidas_raw = crear_medidas_cursor()
    medidas_smooth = crear_medidas_cursor()
    medidas_pipe = crear_medidas_cursor()

    frames_totales = 0
    frames_validos = 0
    frames_sin_cara = 0

    try:
        print("Iniciando cámara y modelo facial...")
        camara.start()
        tracker.start()

        yaw_centro, pitch_centro = calibrar(camara, tracker)

        centro_x, centro_y = cursor.reset_to_center()
        smoother.reset(centro_x, centro_y)
        precision.reset(centro_x, centro_y)

        print("\nCalentamiento de", SEGUNDOS_CALENTAMIENTO, "segundos.")
        inicio = time.perf_counter()

        while time.perf_counter() - inicio < SEGUNDOS_CALENTAMIENTO:
            datos_cara = leer_datos_cara(camara, tracker)

            if cara_valida(datos_cara):
                actualizar_cursores(
                    datos_cara,
                    yaw_centro,
                    pitch_centro,
                    cursor,
                    smoother,
                    precision,
                )

        print("\nMedición")
        print("Mantén la cabeza quieta durante", SEGUNDOS_MEDICION, "segundos.")

        inicio = time.perf_counter()

        while time.perf_counter() - inicio < SEGUNDOS_MEDICION:
            frames_totales += 1
            datos_cara = leer_datos_cara(camara, tracker)

            if not cara_valida(datos_cara):
                frames_sin_cara += 1
                cortar_trayectoria(medidas_raw, medidas_smooth, medidas_pipe)
                continue

            frames_validos += 1

            raw_x, raw_y, smooth_x, smooth_y, pipe_x, pipe_y = actualizar_cursores(
                datos_cara,
                yaw_centro,
                pitch_centro,
                cursor,
                smoother,
                precision,
            )

            guardar_posicion(medidas_raw, raw_x, raw_y)
            guardar_posicion(medidas_smooth, smooth_x, smooth_y)
            guardar_posicion(medidas_pipe, pipe_x, pipe_y)

        print("\nPrueba terminada.")
        print("Frames totales:", frames_totales)
        print("Frames válidos:", frames_validos)
        print("Frames sin cara:", frames_sin_cara)

        imprimir_resultados("raw", medidas_raw)
        imprimir_resultados("smooth", medidas_smooth)
        imprimir_resultados("pipe", medidas_pipe)

    except KeyboardInterrupt:
        print("\nPrueba cancelada por el usuario.")

    finally:
        tracker.stop()
        camara.stop()


if __name__ == "__main__":
    main()
