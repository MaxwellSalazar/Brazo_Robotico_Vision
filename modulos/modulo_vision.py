# =============================================================================
# modulos/modulo_vision.py
# Responsabilidad ÚNICA: capturar cámara, detectar fruta, publicar posición.
#
# FUENTE ORIGINAL: script 1 (control_robot.py)
# Extraído de: reconocer_fruta(), set_sliders(), leer_sliders(), loop cámara
#
# Publica en q_vision:
#   {
#     "cx": int,        # centro X de la fruta en px
#     "cy": int,        # centro Y de la fruta en px
#     "radio": int,     # radio del círculo circunscrito
#     "fruta": str,     # nombre del preset activo
#     "frame": ndarray  # frame BGR para el dashboard (puede desactivarse)
#   }
#   — o None si no hay detección en ese frame.
#
# Recibe en q_config (opcional):
#   {"fruta": "Naranja"}              → cambia preset HSV
#   {"hsv": [h,s,v,h,s,v]}           → ajuste fino manual
#
# NO conoce motores, sensores ni dashboard.
# =============================================================================

import time
import queue

import cv2
import numpy as np

from config import (
    CAMARA_ID, CAM_ANCHO, CAM_ALTO,
    HSV_PRESETS, FRUTA_DEFAULT, AREA_MIN
)


def _detectar(frame, hsv_vals):
    """
    Aplica filtro HSV y devuelve (cx, cy, radio) o (None, None, None).
    Lógica idéntica a reconocer_fruta() del script original.
    """
    hmin, smin, vmin, hmax, smax, vmax = hsv_vals
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([hmin, smin, vmin]),
                            np.array([hmax, smax, vmax]))

    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    if contornos:
        c = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(c) > AREA_MIN:
            (x, y), r = cv2.minEnclosingCircle(c)
            return int(x), int(y), int(r)

    return None, None, None


# ---------------------------------------------------------------------------
# Punto de entrada llamado por main.py
# ---------------------------------------------------------------------------

def run(q_vision, q_config=None):
    """
    Proceso independiente de visión.
    Captura frames, detecta fruta y publica resultados en q_vision.
    """
    print("[VISION] Módulo iniciado")

    cap = cv2.VideoCapture(CAMARA_ID)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  CAM_ANCHO)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_ALTO)

    if not cap.isOpened():
        print("[VISION] ERROR: no se pudo abrir la cámara")
        return

    fruta_activa = FRUTA_DEFAULT
    hsv_vals     = HSV_PRESETS[fruta_activa].copy()

    try:
        while True:
            # --- Cambio de configuración en caliente ---
            if q_config is not None:
                try:
                    cfg = q_config.get_nowait()
                    if 'fruta' in cfg and cfg['fruta'] in HSV_PRESETS:
                        fruta_activa = cfg['fruta']
                        hsv_vals     = HSV_PRESETS[fruta_activa].copy()
                        print(f"[VISION] Preset cambiado a: {fruta_activa}")
                    if 'hsv' in cfg:
                        hsv_vals = cfg['hsv']
                except queue.Empty:
                    pass

            # --- Captura y detección ---
            ret, frame = cap.read()
            if not ret:
                print("[VISION] WARN: frame no leído, reintentando...")
                time.sleep(0.1)
                continue

            cx, cy, radio = _detectar(frame, hsv_vals)

            # Dibujar círculo sobre el frame (útil para el dashboard)
            frame_anotado = frame.copy()
            if cx is not None:
                cv2.circle(frame_anotado, (cx, cy), radio, (0, 255, 0), 2)
                cv2.circle(frame_anotado, (cx, cy), 4,     (0, 255, 0), -1)

            # --- Publicar resultado ---
            dato = {
                "fruta":  fruta_activa,
                "hsv":    hsv_vals,
                "frame":  frame_anotado,   # el dashboard lo usa para mostrar video
                "cx":     cx,
                "cy":     cy,
                "radio":  radio,
                "detectado": cx is not None,
            }

            # put_nowait: si la cola está llena, descartar (no bloquear)
            try:
                q_vision.put_nowait(dato)
            except queue.Full:
                pass

            time.sleep(1 / 30)   # ~30 fps

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        print("[VISION] Cámara liberada — módulo detenido")
