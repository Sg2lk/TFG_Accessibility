import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np


CAMARA = 0
SEGUNDOS_CALIBRACION = 3
SEGUNDOS_CALENTAMIENTO = 1
SEGUNDOS_POR_PUNTO = 6
SEGUNDOS_ENTRADA = 1.5

RADIO_OBJETIVO = 35
RADIO_CURSOR = 8

VENTANA = "Prueba de precision por puntos"


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


def porcentaje_menor_o_igual(valores, limite):
    if len(valores) == 0:
        return 0.0

    contador = 0

    for valor in valores:
        if valor <= limite:
            contador += 1

    return contador * 100 / len(valores)


def crear_medidas():
    return {
        "errores": [],
        "frames": 0,
    }


def crear_resultados(puntos):
    resultados = {
        "raw": {},
        "smooth": {},
        "pipe": {},
    }

    for nombre, x, y in puntos:
        resultados["raw"][nombre] = crear_medidas()
        resultados["smooth"][nombre] = crear_medidas()
        resultados["pipe"][nombre] = crear_medidas()

    return resultados


def guardar_error(resultados, nombre_cursor, nombre_punto, cursor_x, cursor_y, objetivo_x, objetivo_y):
    dx = cursor_x - objetivo_x
    dy = cursor_y - objetivo_y
    error = math.sqrt(dx * dx + dy * dy)

    resultados[nombre_cursor][nombre_punto]["errores"].append(error)
    resultados[nombre_cursor][nombre_punto]["frames"] += 1


def obtener_errores_totales(resultados, nombre_cursor):
    errores = []

    for nombre_punto in resultados[nombre_cursor]:
        errores_punto = resultados[nombre_cursor][nombre_punto]["errores"]
        errores.extend(errores_punto)

    return errores


def imprimir_resumen_cursor(resultados, nombre_cursor):
    errores = obtener_errores_totales(resultados, nombre_cursor)

    print("\n" + "=" * 70)
    print("Cursor:", nombre_cursor)
    print("=" * 70)
    print("Muestras medidas:", len(errores))
    print("Error medio respecto al punto: %.2f px" % media(errores))
    print("Mediana del error:             %.2f px" % mediana(errores))
    print("p95 del error:                 %.2f px" % percentil_95(errores))

    if len(errores) > 0:
        print("Error maximo:                  %.2f px" % max(errores))
    else:
        print("Error maximo:                  0.00 px")

    print("Frames dentro de 30 px:        %.2f %%" % porcentaje_menor_o_igual(errores, 30))
    print("Frames dentro de 50 px:        %.2f %%" % porcentaje_menor_o_igual(errores, 50))

    print("\nDetalle por zona:")

    for nombre_punto in resultados[nombre_cursor]:
        errores_punto = resultados[nombre_cursor][nombre_punto]["errores"]
        frames = resultados[nombre_cursor][nombre_punto]["frames"]

        print("-", nombre_punto)
        print("  Frames:", frames)
        print("  Error medio: %.2f px" % media(errores_punto))
        print("  p95:         %.2f px" % percentil_95(errores_punto))
        print("  Dentro 50:   %.2f %%" % porcentaje_menor_o_igual(errores_punto, 50))


def crear_puntos(ancho, alto):
    margen_x = 0.20
    centro_x = 0.50
    derecha_x = 0.80

    arriba_y = 0.20
    centro_y = 0.50
    abajo_y = 0.80

    puntos = [
        ("arriba izquierda", int(ancho * margen_x), int(alto * arriba_y)),
        ("arriba centro", int(ancho * centro_x), int(alto * arriba_y)),
        ("arriba derecha", int(ancho * derecha_x), int(alto * arriba_y)),
        ("centro izquierda", int(ancho * margen_x), int(alto * centro_y)),
        ("centro", int(ancho * centro_x), int(alto * centro_y)),
        ("centro derecha", int(ancho * derecha_x), int(alto * centro_y)),
        ("abajo izquierda", int(ancho * margen_x), int(alto * abajo_y)),
        ("abajo centro", int(ancho * centro_x), int(alto * abajo_y)),
        ("abajo derecha", int(ancho * derecha_x), int(alto * abajo_y)),
    ]

    return puntos


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
    print("\nCalibracion")
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
        raise RuntimeError("No se ha detectado la cara durante la calibracion.")

    yaw_centro = media(muestras_yaw)
    pitch_centro = media(muestras_pitch)

    print("Calibracion completada con", len(muestras_yaw), "frames validos.")
    return yaw_centro, pitch_centro


def actualizar_cursores(datos_cara, yaw_centro, pitch_centro, cursor, smoother, precision):
    yaw = datos_cara.get("yaw")
    pitch = datos_cara.get("pitch")

    raw_x, raw_y = cursor.update(yaw, pitch, yaw_centro, pitch_centro)
    smooth_x, smooth_y = smoother.update(raw_x, raw_y)
    pipe_x, pipe_y = precision.update(smooth_x, smooth_y)

    return raw_x, raw_y, smooth_x, smooth_y, pipe_x, pipe_y


def limitar(valor, minimo, maximo):
    if valor < minimo:
        return minimo

    if valor > maximo:
        return maximo

    return valor


def dibujar_cursor(pantalla, x, y, texto, color):
    alto, ancho = pantalla.shape[:2]

    x = int(limitar(x, 0, ancho - 1))
    y = int(limitar(y, 0, alto - 1))

    cv2.circle(pantalla, (x, y), RADIO_CURSOR, color, -1)
    cv2.putText(
        pantalla,
        texto,
        (x + 12, y - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2,
    )


def dibujar_pantalla(ancho, alto, nombre_punto, objetivo_x, objetivo_y, tiempo_restante, midiendo, datos_cara_validos, posiciones):
    pantalla = np.zeros((alto, ancho, 3), dtype=np.uint8)

    if midiendo:
        texto_estado = "MIDIENDO: manten el cursor sobre el punto"
        color_objetivo = (0, 255, 0)
    else:
        texto_estado = "MUEVETE hacia el punto"
        color_objetivo = (0, 180, 255)

    cv2.circle(pantalla, (objetivo_x, objetivo_y), RADIO_OBJETIVO, color_objetivo, 3)
    cv2.circle(pantalla, (objetivo_x, objetivo_y), 5, color_objetivo, -1)

    cv2.putText(
        pantalla,
        "Punto: " + nombre_punto,
        (40, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        pantalla,
        texto_estado,
        (40, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        pantalla,
        "Tiempo restante: %.1f s" % tiempo_restante,
        (40, 145),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        pantalla,
        "ESC: cancelar",
        (40, alto - 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (180, 180, 180),
        2,
    )

    if not datos_cara_validos:
        cv2.putText(
            pantalla,
            "Cara no detectada",
            (40, 190),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 0, 255),
            2,
        )

    if posiciones is not None:
        raw_x, raw_y, smooth_x, smooth_y, pipe_x, pipe_y = posiciones
        dibujar_cursor(pantalla, raw_x, raw_y, "raw", (255, 255, 255))
        dibujar_cursor(pantalla, smooth_x, smooth_y, "smooth", (255, 0, 255))
        dibujar_cursor(pantalla, pipe_x, pipe_y, "pipe", (255, 255, 0))

    return pantalla


def preparar_ventana(ancho, alto):
    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VENTANA, ancho, alto)
    cv2.setWindowProperty(VENTANA, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


def main():
    load_and_apply_user_config(settings)

    camara = Camera(camera_index=CAMARA)
    tracker = FaceTracker()

    cursor = CursorProcessor()
    smoother = PositionSmoother()
    precision = PrecisionStabilizer()

    ancho, alto = cursor.get_screen_size()
    puntos = crear_puntos(ancho, alto)
    resultados = crear_resultados(puntos)

    frames_totales = 0
    frames_validos = 0
    frames_sin_cara = 0
    prueba_cancelada = False

    try:
        print("Iniciando camara y modelo facial...")
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

        preparar_ventana(ancho, alto)

        print("\nPrueba de precision por puntos")
        print("Mueve el cursor hacia cada punto y mantenlo estable.")
        print("Los primeros", SEGUNDOS_ENTRADA, "segundos de cada punto no se miden.")

        for nombre_punto, objetivo_x, objetivo_y in puntos:
            inicio_punto = time.perf_counter()
            posiciones = None

            while time.perf_counter() - inicio_punto < SEGUNDOS_POR_PUNTO:
                tiempo_actual = time.perf_counter()
                tiempo_transcurrido = tiempo_actual - inicio_punto
                tiempo_restante = SEGUNDOS_POR_PUNTO - tiempo_transcurrido
                midiendo = tiempo_transcurrido >= SEGUNDOS_ENTRADA

                frames_totales += 1
                datos_cara = leer_datos_cara(camara, tracker)
                datos_cara_validos = cara_valida(datos_cara)

                if datos_cara_validos:
                    frames_validos += 1

                    posiciones = actualizar_cursores(
                        datos_cara,
                        yaw_centro,
                        pitch_centro,
                        cursor,
                        smoother,
                        precision,
                    )

                    raw_x, raw_y, smooth_x, smooth_y, pipe_x, pipe_y = posiciones

                    if midiendo:
                        guardar_error(resultados, "raw", nombre_punto, raw_x, raw_y, objetivo_x, objetivo_y)
                        guardar_error(resultados, "smooth", nombre_punto, smooth_x, smooth_y, objetivo_x, objetivo_y)
                        guardar_error(resultados, "pipe", nombre_punto, pipe_x, pipe_y, objetivo_x, objetivo_y)
                else:
                    frames_sin_cara += 1

                pantalla = dibujar_pantalla(
                    ancho,
                    alto,
                    nombre_punto,
                    objetivo_x,
                    objetivo_y,
                    tiempo_restante,
                    midiendo,
                    datos_cara_validos,
                    posiciones,
                )

                cv2.imshow(VENTANA, pantalla)
                tecla = cv2.waitKey(1) & 0xFF

                if tecla == 27:
                    prueba_cancelada = True
                    break

            if prueba_cancelada:
                break

        cv2.destroyWindow(VENTANA)

        print("\nPrueba terminada.")
        print("Frames totales:", frames_totales)
        print("Frames validos:", frames_validos)
        print("Frames sin cara:", frames_sin_cara)

        imprimir_resumen_cursor(resultados, "raw")
        imprimir_resumen_cursor(resultados, "smooth")
        imprimir_resumen_cursor(resultados, "pipe")

    except KeyboardInterrupt:
        print("\nPrueba cancelada por el usuario.")

    finally:
        cv2.destroyAllWindows()
        tracker.stop()
        camara.stop()


if __name__ == "__main__":
    main()
