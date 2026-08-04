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
SEGUNDOS_CALIBRACION = 3
SEGUNDOS_CALENTAMIENTO = 1
SEGUNDOS_MEDICION = 15
VENTANA = "Estabilidad del cursor en reposo"

CARPETA_ACTUAL = Path(__file__).resolve().parent
RESULTADOS_CSV = CARPETA_ACTUAL / "cursor_reposo.csv"
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


ultimo_timestamp_ms = 0


def obtener_timestamp_ms():
    global ultimo_timestamp_ms

    timestamp_ms = int(time.perf_counter() * 1000)
    ultimo_timestamp_ms = max(timestamp_ms, ultimo_timestamp_ms + 1)
    return ultimo_timestamp_ms


def media(valores):
    return sum(valores) / len(valores) if valores else 0.0


def mediana(valores):
    if not valores:
        return 0.0

    ordenados = sorted(valores)
    centro = len(ordenados) // 2

    if len(ordenados) % 2:
        return ordenados[centro]

    return (ordenados[centro - 1] + ordenados[centro]) / 2


def percentil_95(valores):
    if not valores:
        return 0.0

    ordenados = sorted(valores)
    posicion = round(0.95 * (len(ordenados) - 1))
    return ordenados[posicion]


def desviacion_estandar(valores):
    if not valores:
        return 0.0

    valor_medio = media(valores)
    return math.sqrt(sum((valor - valor_medio) ** 2 for valor in valores) / len(valores))


def crear_medidas_cursor():
    return {"x": [], "y": [], "desplazamientos": [], "ultima_posicion": None}


def guardar_posicion(medidas, x, y):
    posicion = (float(x), float(y))

    if medidas["ultima_posicion"] is not None:
        x_anterior, y_anterior = medidas["ultima_posicion"]
        medidas["desplazamientos"].append(
            math.hypot(posicion[0] - x_anterior, posicion[1] - y_anterior)
        )

    medidas["x"].append(posicion[0])
    medidas["y"].append(posicion[1])
    medidas["ultima_posicion"] = posicion


def cortar_trayectoria(*medidas):
    for conjunto in medidas:
        conjunto["ultima_posicion"] = None


def numero_csv(valor):
    return f"{valor:.2f}".replace(".", ",")


def obtener_numero_ejecucion():
    if not RESULTADOS_CSV.exists() or RESULTADOS_CSV.stat().st_size == 0:
        return 1

    ejecuciones = set()

    with RESULTADOS_CSV.open("r", newline="", encoding="utf-8-sig") as archivo:
        lector = csv.DictReader(archivo, delimiter=";")

        for fila in lector:
            ejecucion = (fila.get("Ejecución") or "").strip()

            if ejecucion:
                ejecuciones.add(ejecucion)

    return len(ejecuciones) + 1


def crear_fila_resultados(ejecucion, nombre, medidas):
    desplazamientos = medidas["desplazamientos"]
    mayores_10 = sum(desplazamiento > 10 for desplazamiento in desplazamientos)
    porcentaje_mayores_10 = (
        mayores_10 * 100 / len(desplazamientos) if desplazamientos else 0.0
    )

    return [
        ejecucion,
        nombre,
        len(medidas["x"]),
        numero_csv(media(desplazamientos)),
        numero_csv(mediana(desplazamientos)),
        numero_csv(percentil_95(desplazamientos)),
        numero_csv(max(desplazamientos) if desplazamientos else 0.0),
        numero_csv(porcentaje_mayores_10),
        numero_csv(desviacion_estandar(medidas["x"])),
        numero_csv(desviacion_estandar(medidas["y"])),
    ]


def guardar_csv(medidas_raw, medidas_smooth, medidas_pipe):
    archivo_existente = RESULTADOS_CSV.exists() and RESULTADOS_CSV.stat().st_size > 0
    ejecucion = obtener_numero_ejecucion()
    resultados = [
        ("raw", medidas_raw),
        ("smooth", medidas_smooth),
        ("pipe", medidas_pipe),
    ]

    with RESULTADOS_CSV.open("a", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.writer(archivo, delimiter=";")

        if not archivo_existente:
            escritor.writerow([
                "Ejecución",
                "Cursor",
                "Frames válidos",
                "Desplazamiento medio (px)",
                "Mediana desplazamiento (px)",
                "p95 desplazamiento (px)",
                "Máximo desplazamiento (px)",
                "Desplazamientos > 10 px (%)",
                "Desviación estándar X (px)",
                "Desviación estándar Y (px)",
            ])

        for nombre, medidas in resultados:
            escritor.writerow(crear_fila_resultados(ejecucion, nombre, medidas))


def leer_frame_y_datos(camara, tracker):
    frame = camara.read_frame()

    if frame is None:
        return None, None

    datos_cara = tracker.detect(frame, timestamp_ms=obtener_timestamp_ms())
    return frame, datos_cara


def cara_valida(datos_cara):
    return bool(
        datos_cara
        and datos_cara.get("face_detected")
        and datos_cara.get("yaw") is not None
        and datos_cara.get("pitch") is not None
    )


def limitar(valor, minimo, maximo):
    return max(minimo, min(valor, maximo))


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
    ancho_maximo = int(ancho_pantalla * 0.60)
    alto_maximo = int(alto_pantalla * 0.72)

    ancho_ventana = ancho_maximo
    alto_ventana = int(ancho_ventana / proporcion)

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


def dibujar_pipe(imagen, pipe_x, pipe_y, ancho_pantalla, alto_pantalla):
    alto_frame, ancho_frame = imagen.shape[:2]
    pipe_x = limitar(int(pipe_x), 0, ancho_pantalla - 1)
    pipe_y = limitar(int(pipe_y), 0, alto_pantalla - 1)
    dibujo_x = round(pipe_x * (ancho_frame - 1) / max(1, ancho_pantalla - 1))
    dibujo_y = round(pipe_y * (alto_frame - 1) / max(1, alto_pantalla - 1))

    cv2.circle(imagen, (dibujo_x, dibujo_y), 9, (0, 255, 0), -1, cv2.LINE_AA)


def mostrar_interfaz(
    frame,
    estado,
    segundos_restantes,
    ancho_pantalla,
    alto_pantalla,
    pipe_x=None,
    pipe_y=None,
):
    imagen = frame.copy()
    dibujar_cruz(imagen)

    if pipe_x is not None and pipe_y is not None:
        dibujar_pipe(imagen, pipe_x, pipe_y, ancho_pantalla, alto_pantalla)

    textos = [
        estado,
        f"Tiempo restante: {segundos_restantes:.1f} s",
        "Cruz blanca: referencia central",
        "ESC: cancelar",
    ]

    if pipe_x is not None and pipe_y is not None:
        textos.insert(3, "Punto verde: cursor PIPE")

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

    cv2.imshow(VENTANA, imagen)
    return (cv2.waitKey(1) & 0xFF) != 27


def calibrar(camara, tracker, ancho_pantalla, alto_pantalla):
    muestras_yaw = []
    muestras_pitch = []
    inicio = time.perf_counter()

    while time.perf_counter() - inicio < SEGUNDOS_CALIBRACION:
        frame, datos_cara = leer_frame_y_datos(camara, tracker)

        if frame is None:
            continue

        if cara_valida(datos_cara):
            muestras_yaw.append(float(datos_cara["yaw"]))
            muestras_pitch.append(float(datos_cara["pitch"]))

        segundos_restantes = max(
            0.0, SEGUNDOS_CALIBRACION - (time.perf_counter() - inicio)
        )

        if not mostrar_interfaz(
            frame,
            "Calibración: mira a la cruz",
            segundos_restantes,
            ancho_pantalla,
            alto_pantalla,
        ):
            raise KeyboardInterrupt

    if not muestras_yaw:
        raise RuntimeError("No se ha detectado la cara durante la calibración.")

    return media(muestras_yaw), media(muestras_pitch)


def actualizar_cursores(datos_cara, yaw_centro, pitch_centro, cursor, smoother, precision):
    raw_x, raw_y = cursor.update(
        datos_cara["yaw"], datos_cara["pitch"], yaw_centro, pitch_centro
    )
    smooth_x, smooth_y = smoother.update(raw_x, raw_y)
    pipe_x, pipe_y = precision.update(smooth_x, smooth_y)
    return raw_x, raw_y, smooth_x, smooth_y, pipe_x, pipe_y


def obtener_frame_inicial(camara):
    limite = time.perf_counter() + 5

    while time.perf_counter() < limite:
        frame = camara.read_frame()

        if frame is not None:
            return frame

    raise RuntimeError("No se ha podido obtener una imagen de la cámara.")


def main():
    load_and_apply_user_config(settings)

    camara = Camera(camera_index=CAMARA)
    tracker = FaceTracker()
    cursor = CursorProcessor()
    smoother = PositionSmoother()
    precision = PrecisionStabilizer()
    ancho_pantalla, alto_pantalla = cursor.get_screen_size()

    medidas_raw = crear_medidas_cursor()
    medidas_smooth = crear_medidas_cursor()
    medidas_pipe = crear_medidas_cursor()

    try:
        print("Iniciando prueba...")
        camara.start()
        tracker.start()

        frame_inicial = obtener_frame_inicial(camara)
        preparar_ventana(frame_inicial, ancho_pantalla, alto_pantalla)
        yaw_centro, pitch_centro = calibrar(
            camara, tracker, ancho_pantalla, alto_pantalla
        )

        centro_x, centro_y = cursor.reset_to_center()
        smoother.reset(centro_x, centro_y)
        precision.reset(centro_x, centro_y)
        pipe_x, pipe_y = centro_x, centro_y

        inicio = time.perf_counter()

        while time.perf_counter() - inicio < SEGUNDOS_CALENTAMIENTO:
            frame, datos_cara = leer_frame_y_datos(camara, tracker)

            if frame is None:
                continue

            if cara_valida(datos_cara):
                _, _, _, _, pipe_x, pipe_y = actualizar_cursores(
                    datos_cara, yaw_centro, pitch_centro, cursor, smoother, precision
                )

            segundos_restantes = max(
                0.0, SEGUNDOS_CALENTAMIENTO - (time.perf_counter() - inicio)
            )

            if not mostrar_interfaz(
                frame,
                "Calentamiento: mantente quieto",
                segundos_restantes,
                ancho_pantalla,
                alto_pantalla,
                pipe_x,
                pipe_y,
            ):
                raise KeyboardInterrupt

        inicio = time.perf_counter()

        while time.perf_counter() - inicio < SEGUNDOS_MEDICION:
            frame, datos_cara = leer_frame_y_datos(camara, tracker)

            if frame is None:
                continue

            if cara_valida(datos_cara):
                raw_x, raw_y, smooth_x, smooth_y, pipe_x, pipe_y = actualizar_cursores(
                    datos_cara, yaw_centro, pitch_centro, cursor, smoother, precision
                )
                guardar_posicion(medidas_raw, raw_x, raw_y)
                guardar_posicion(medidas_smooth, smooth_x, smooth_y)
                guardar_posicion(medidas_pipe, pipe_x, pipe_y)
            else:
                cortar_trayectoria(medidas_raw, medidas_smooth, medidas_pipe)

            segundos_restantes = max(
                0.0, SEGUNDOS_MEDICION - (time.perf_counter() - inicio)
            )

            if not mostrar_interfaz(
                frame,
                "Medición: mantente quieto",
                segundos_restantes,
                ancho_pantalla,
                alto_pantalla,
                pipe_x,
                pipe_y,
            ):
                raise KeyboardInterrupt

        guardar_csv(medidas_raw, medidas_smooth, medidas_pipe)
        print("Prueba terminada. Resultados guardados en el CSV.")

    except KeyboardInterrupt:
        print("Prueba cancelada. No se han guardado resultados.")
    except Exception as error:
        print(f"Error: {error}")
    finally:
        tracker.stop()
        camara.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()