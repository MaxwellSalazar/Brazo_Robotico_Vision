# =============================================================================
# modulos/modulo_logger.py
# Responsabilidad ÚNICA: escuchar todos los canales y guardar datos en CSV.
#
# FUENTE ORIGINAL: NO existía — es NUEVO, esencial para las publicaciones.
#
# Genera un CSV por sesión con nombre basado en timestamp:
#   datos/sesion_2026-03-19_14-32-05.csv
#
# Columnas registradas:
#   timestamp, fruta, detectado, cx, cy, radio,
#   corriente_A, voltaje_V, potencia_W, energia_J
#
# NO conoce motores, visión artificial ni dashboard.
# =============================================================================

import os
import csv
import time
import queue
from datetime import datetime

from config import DATOS_DIR, LOG_FREQ_HZ


def _nombre_archivo():
    ts  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(DATOS_DIR, exist_ok=True)
    return os.path.join(DATOS_DIR, f"sesion_{ts}.csv")


COLUMNAS = [
    "timestamp",
    "fruta", "detectado", "cx", "cy", "radio",
    "corriente_A", "voltaje_V", "potencia_W", "energia_J",
]


# ---------------------------------------------------------------------------
# Punto de entrada llamado por main.py
# ---------------------------------------------------------------------------

def run(q_vision, q_sensores):
    """
    Proceso independiente de logger.
    Combina datos de visión y sensores en un CSV por sesión.
    """
    archivo = _nombre_archivo()
    print(f"[LOGGER] Módulo iniciado → {archivo}")

    intervalo       = 1.0 / LOG_FREQ_HZ
    ultimo_vision   = {}
    ultimo_sensores = {}

    try:
        with open(archivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNAS)
            writer.writeheader()
            f.flush()

            while True:
                # Vaciar colas sin bloquear — quedarse con el dato más reciente
                while True:
                    try:
                        dato = q_vision.get_nowait()
                        # No guardamos el frame (numpy array) en el CSV
                        ultimo_vision = {k: v for k, v in dato.items()
                                         if k != 'frame'}
                    except queue.Empty:
                        break

                while True:
                    try:
                        ultimo_sensores = q_sensores.get_nowait()
                    except queue.Empty:
                        break

                # Combinar y escribir fila
                if ultimo_vision or ultimo_sensores:
                    fila = {
                        "timestamp":   round(time.time(), 4),
                        # Visión
                        "fruta":       ultimo_vision.get("fruta",     ""),
                        "detectado":   ultimo_vision.get("detectado", False),
                        "cx":          ultimo_vision.get("cx",        ""),
                        "cy":          ultimo_vision.get("cy",        ""),
                        "radio":       ultimo_vision.get("radio",     ""),
                        # Sensores
                        "corriente_A": ultimo_sensores.get("corriente_A", ""),
                        "voltaje_V":   ultimo_sensores.get("voltaje_V",   ""),
                        "potencia_W":  ultimo_sensores.get("potencia_W",  ""),
                        "energia_J":   ultimo_sensores.get("energia_J",   ""),
                    }
                    writer.writerow(fila)
                    f.flush()   # escritura inmediata — no perder datos si cae

                time.sleep(intervalo)

    except KeyboardInterrupt:
        pass
    finally:
        print(f"[LOGGER] Archivo guardado: {archivo}")
        print("[LOGGER] Módulo detenido")
