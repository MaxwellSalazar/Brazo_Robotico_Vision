# =============================================================================
# modulos/modulo_motores.py
# Responsabilidad ÚNICA: mover los motores stepper.
#
# FUENTE ORIGINAL: script 1 (control_robot.py)
# Extraído de: mover_motor(), control_manual(), alinear(), loop GPIO
#
# Recibe mensajes de dos colas:
#   q_vision   → dict con {"cx", "cy"} cuando hay fruta detectada (modo AUTO)
#   q_comandos → dict con {"accion": "base_izq" | "base_der" | ...} (modo MANUAL)
#
# NO conoce nada de cámaras, sensores ni dashboard.
# =============================================================================

import time
import queue

from gpio_wrapper import get_gpio
from config import MOTORES, PASOS_MANUAL, DELAY_STEP, MARGEN_AUTO, CAM_ANCHO, CAM_ALTO

GPIO = get_gpio()


def _inicializar_gpio():
    GPIO.setmode(GPIO.BCM)
    for m in MOTORES.values():
        GPIO.setup(m['DIR'], GPIO.OUT)
        GPIO.setup(m['STEP'], GPIO.OUT)


def _mover_motor(nombre, direccion, pasos, delay=DELAY_STEP):
    """Envía pulsos de paso al motor indicado."""
    motor = MOTORES[nombre]
    GPIO.output(motor['DIR'], direccion)
    for _ in range(pasos):
        GPIO.output(motor['STEP'], GPIO.HIGH)
        time.sleep(delay)
        GPIO.output(motor['STEP'], GPIO.LOW)
        time.sleep(delay)


def _alinear(cx, cy):
    """
    Modo AUTO: calcula cuánto moverse según la posición de la fruta.
    Mismo algoritmo que alinear() del script original.
    """
    centro_x = CAM_ANCHO // 2
    centro_y = CAM_ALTO  // 2
    dx = cx - centro_x
    dy = cy - centro_y

    if abs(dx) > MARGEN_AUTO:
        pasos = int(abs(dx) * 0.2)
        dir_  = GPIO.LOW if dx > 0 else GPIO.HIGH
        _mover_motor('base', dir_, pasos)

    if abs(dy) > MARGEN_AUTO:
        pasos = int(abs(dy) * 0.2)
        dir_  = GPIO.HIGH if dy < 0 else GPIO.LOW
        _mover_motor('antebrazo', dir_, pasos)


def _ejecutar_comando(accion):
    """
    Modo MANUAL: ejecuta el comando recibido desde el dashboard o teclado.
    Mapeo idéntico al control_manual() del script original.
    """
    mapa = {
        'base_izq':      ('base',      GPIO.LOW),
        'base_der':      ('base',      GPIO.HIGH),
        'antebrazo_sub': ('antebrazo', GPIO.HIGH),
        'antebrazo_baj': ('antebrazo', GPIO.LOW),
        'brazo1_sub':    ('brazo_1',   GPIO.HIGH),
        'brazo1_baj':    ('brazo_1',   GPIO.LOW),
        'brazo2_sub':    ('brazo_2',   GPIO.HIGH),
        'brazo2_baj':    ('brazo_2',   GPIO.LOW),
    }
    if accion in mapa:
        motor, direccion = mapa[accion]
        _mover_motor(motor, direccion, PASOS_MANUAL)


# ---------------------------------------------------------------------------
# Punto de entrada llamado por main.py
# ---------------------------------------------------------------------------

def run(q_vision, q_comandos):
    """
    Proceso independiente de motores.
    Escucha visión (AUTO) y comandos manuales (MANUAL) de forma no bloqueante.
    """
    print("[MOTORES] Módulo iniciado")
    _inicializar_gpio()
    modo = "AUTO"

    try:
        while True:
            # --- Leer comando de modo/manual (prioridad alta) ---
            try:
                cmd = q_comandos.get_nowait()
                if cmd.get('tipo') == 'modo':
                    modo = cmd['valor']
                    print(f"[MOTORES] Modo cambiado a: {modo}")
                elif cmd.get('tipo') == 'accion' and modo == "MANUAL":
                    _ejecutar_comando(cmd['valor'])
            except queue.Empty:
                pass

            # --- Leer datos de visión (modo AUTO) ---
            if modo == "AUTO":
                try:
                    dato = q_vision.get_nowait()
                    if 'cx' in dato and 'cy' in dato:
                        _alinear(dato['cx'], dato['cy'])
                except queue.Empty:
                    pass

            time.sleep(0.01)   # evita busy-loop que satura la CPU

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
        print("[MOTORES] GPIO liberado — módulo detenido")
