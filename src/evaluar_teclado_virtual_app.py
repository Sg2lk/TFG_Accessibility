import os
import sys
import time
import subprocess
import tkinter as tk


FRASES = [
    "hola mundo",
    "prueba de teclado virtual",
    "control por cabeza",
    "este sistema permite escribir con la cabeza",
]

proceso_app = None
ventana = None
entrada = None
frase_label = None
estado_label = None
texto = None

indice = 0
inicio = None
backspaces = 0
resultados = []


def contar_errores(objetivo, escrito):
    errores = abs(len(objetivo) - len(escrito))
    limite = min(len(objetivo), len(escrito))

    for i in range(limite):
        if objetivo[i] != escrito[i]:
            errores += 1

    return errores


def lanzar_aplicacion():
    carpeta = os.path.dirname(os.path.abspath(__file__))

    if not os.path.isdir(os.path.join(carpeta, "src")):
        print("No encuentro la carpeta src. Abre la aplicacion manualmente si hace falta.")
        return None

    respuesta = input("Quieres abrir la aplicacion del proyecto? (s/n): ").strip().lower()
    if respuesta != "s":
        return None

    comando = [sys.executable, "-m", "src.main"]

    try:
        if os.name == "nt":
            return subprocess.Popen(
                comando,
                cwd=carpeta,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        return subprocess.Popen(comando, cwd=carpeta)
    except Exception as error:
        print("No se pudo abrir la aplicacion:", error)
        return None


def preparar_frase():
    global inicio, backspaces

    inicio = None
    backspaces = 0
    texto.set("")

    frase = FRASES[indice]
    frase_label.config(text=f"Frase {indice + 1}/{len(FRASES)}: {frase}")
    estado_label.config(text="Esperando escritura...")
    entrada.config(state="normal")
    entrada.focus_force()


def detectar_inicio(*args):
    global inicio

    if inicio is None and texto.get() != "":
        inicio = time.time()
        estado_label.config(text="Escribiendo...")


def contar_tecla(event):
    global backspaces

    if event.keysym == "BackSpace":
        backspaces += 1


def terminar_frase(event=None):
    global indice

    if inicio is None:
        return "break"

    objetivo = FRASES[indice]
    escrito = texto.get()
    tiempo = time.time() - inicio

    errores = contar_errores(objetivo, escrito)
    correctos = max(0, len(objetivo) - errores)

    cpm = 0
    if tiempo > 0:
        cpm = correctos / (tiempo / 60)

    precision = 0
    if len(objetivo) > 0:
        precision = correctos / len(objetivo) * 100

    exito = escrito == objetivo

    resultado = {
        "objetivo": objetivo,
        "escrito": escrito,
        "tiempo": tiempo,
        "cpm": cpm,
        "errores": errores,
        "correcciones": backspaces,
        "precision": precision,
        "exito": exito,
    }

    resultados.append(resultado)
    imprimir_resultado(resultado)

    indice += 1
    if indice < len(FRASES):
        preparar_frase()
    else:
        terminar_prueba()

    return "break"


def imprimir_resultado(r):
    print("\n" + "=" * 55)
    print("Frase objetivo:", r["objetivo"])
    print("Texto escrito:  ", r["escrito"])
    print("Exito:          ", "SI" if r["exito"] else "NO")
    print(f"Tiempo:         {r['tiempo']:.2f} s")
    print(f"Caracteres/min: {r['cpm']:.2f}")
    print("Errores:        ", r["errores"])
    print("Correcciones:   ", r["correcciones"])
    print(f"Precision:      {r['precision']:.2f} %")


def terminar_prueba():
    entrada.config(state="disabled")
    frase_label.config(text="Prueba terminada")
    estado_label.config(text="Resultados impresos por terminal.")
    imprimir_resumen()


def imprimir_resumen():
    total = len(resultados)
    exitos = 0
    tiempo = 0
    cpm = 0
    errores = 0
    correcciones = 0

    for r in resultados:
        if r["exito"]:
            exitos += 1
        tiempo += r["tiempo"]
        cpm += r["cpm"]
        errores += r["errores"]
        correcciones += r["correcciones"]

    print("\n" + "=" * 55)
    print("RESUMEN FINAL")
    print(f"Frases completadas: {total}")
    print(f"Tasa de exito:      {exitos / total * 100:.2f} %")
    print(f"Tiempo medio:       {tiempo / total:.2f} s")
    print(f"CPM medio:          {cpm / total:.2f}")
    print(f"Errores totales:    {errores}")
    print(f"Correcciones:       {correcciones}")
    print("=" * 55)


def mantener_foco():
    if indice < len(FRASES):
        entrada.focus_force()
    ventana.after(800, mantener_foco)


def cerrar():
    ventana.destroy()
    if proceso_app is not None and proceso_app.poll() is None:
        print("\nLa aplicacion sigue abierta. Cierrala desde su propio menu.")


def crear_ventana():
    global ventana, entrada, frase_label, estado_label, texto

    ventana = tk.Tk()
    ventana.title("Evaluacion del teclado virtual")
    ventana.geometry("900x340")
    ventana.protocol("WM_DELETE_WINDOW", cerrar)

    texto = tk.StringVar()
    texto.trace_add("write", detectar_inicio)

    tk.Label(
        ventana,
        text="Evaluacion del teclado virtual",
        font=("Arial", 18, "bold"),
    ).pack(pady=12)

    tk.Label(
        ventana,
        text=(
            "Con esta ventana visible, abre el teclado virtual desde tu aplicacion y escribe aqui.\n"
            "El tiempo empieza con el primer caracter. Pulsa ENTER en el teclado virtual para terminar cada frase."
        ),
        font=("Arial", 11),
    ).pack()

    frase_label = tk.Label(ventana, text="", font=("Arial", 16, "bold"), wraplength=820)
    frase_label.pack(pady=18)

    entrada = tk.Entry(ventana, textvariable=texto, font=("Arial", 18), width=55, justify="center")
    entrada.pack(pady=8)
    entrada.bind("<KeyPress>", contar_tecla)
    entrada.bind("<Return>", terminar_frase)

    estado_label = tk.Label(ventana, text="", font=("Arial", 11))
    estado_label.pack(pady=8)

    preparar_frase()
    mantener_foco()
    ventana.mainloop()


def main():
    global proceso_app

    print("Evaluacion del teclado virtual")
    print("La prueba se hace escribiendo en una ventana externa.")
    print("La calibracion, el cursor y el teclado virtual los gestiona tu aplicacion real.\n")

    proceso_app = lanzar_aplicacion()

    print("\nAntes de empezar:")
    print("1. Calibra el cursor en la aplicacion.")
    print("2. Activa el sistema si esta en pausa.")
    print("3. Pulsa ENTER aqui para mostrar la ventana de evaluacion.")
    print("4. Con la ventana abierta, usa tu aplicacion para abrir el teclado virtual y escribir.")
    input("\nPulsa ENTER aqui cuando quieras mostrar la ventana de evaluacion...")

    crear_ventana()


if __name__ == "__main__":
    main()
