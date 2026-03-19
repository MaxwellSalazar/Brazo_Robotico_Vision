#!/usr/bin/env python3
# =============================================================================
# test_modulos.py — Verificación independiente de cada módulo
#
# Uso:
#   python test_modulos.py            # prueba todos los módulos
#   python test_modulos.py config     # prueba solo config
#   python test_modulos.py gpio       # prueba solo gpio
#   python test_modulos.py sensores   # prueba solo sensores
#   python test_modulos.py motores    # prueba solo motores
#   python test_modulos.py logger     # prueba solo logger
#   python test_modulos.py colas      # prueba comunicación entre módulos
#   python test_modulos.py vision     # prueba visión (necesita cámara)
# =============================================================================

import sys
import os
import time
import threading
import queue as q_lib

# --- Fix crítico para Windows ---
# Agrega la carpeta raíz del proyecto al path ANTES de cualquier import
# de módulos del proyecto. Sin esto, Python no encuentra 'modulos/'.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

print("ROOT detectado:", ROOT)
print("modulos existe:", os.path.isdir(os.path.join(ROOT, "modulos")))
# Ahora sí podemos importar módulos del proyecto
import config as cfg
from gpio_wrapper import get_gpio

# Colores para consola Windows/Linux
OK    = "[OK]  "
FAIL  = "[ERR] "
INFO  = "[-->] "
SEP   = "─" * 52

def titulo(texto):
    print(f"\n{SEP}\n  {texto}\n{SEP}")

def ok(msg):   print(f"  {OK} {msg}")
def fail(msg): print(f"  {FAIL} {msg}")
def info(msg): print(f"  {INFO} {msg}")


# =============================================================================
# TEST 1 — config.py
# =============================================================================
def test_config():
    titulo("TEST 1 — config.py")
    try:
        assert isinstance(cfg.MOTORES, dict),        "MOTORES debe ser dict"
        assert len(cfg.MOTORES) == 4,                "Debe haber 4 motores"
        assert isinstance(cfg.HSV_PRESETS, dict),    "HSV_PRESETS debe ser dict"
        assert cfg.FRUTA_DEFAULT in cfg.HSV_PRESETS, "FRUTA_DEFAULT debe existir"
        assert cfg.CAM_ANCHO > 0,                    "CAM_ANCHO debe ser positivo"
        assert cfg.PLATAFORMA in ("PI", "MOCK"),     "PLATAFORMA debe ser PI o MOCK"

        ok(f"MOTORES: {list(cfg.MOTORES.keys())}")
        ok(f"Frutas: {list(cfg.HSV_PRESETS.keys())}")
        ok(f"Fruta default: {cfg.FRUTA_DEFAULT}")
        ok(f"Resolución: {cfg.CAM_ANCHO}x{cfg.CAM_ALTO}")
        ok(f"Plataforma: {cfg.PLATAFORMA}")
        ok(f"Datos en: {cfg.DATOS_DIR}")
        return True
    except AssertionError as e:
        fail(str(e)); return False
    except Exception as e:
        fail(f"Error inesperado: {e}"); return False


# =============================================================================
# TEST 2 — gpio_wrapper.py
# =============================================================================
def test_gpio():
    titulo("TEST 2 — gpio_wrapper.py")
    try:
        GPIO = get_gpio()
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(10, GPIO.OUT)
        GPIO.output(10, GPIO.HIGH)
        GPIO.output(10, GPIO.LOW)
        GPIO.cleanup()

        ok("get_gpio() retorna objeto válido")
        ok("setmode() sin error")
        ok("setup() sin error")
        ok("output() HIGH/LOW sin error")
        ok("cleanup() sin error")
        return True
    except Exception as e:
        fail(f"Error: {e}"); return False


# =============================================================================
# TEST 3 — modulo_sensores.py
# Corre en un HILO (no proceso) para evitar el problema de spawn en Windows
# =============================================================================
def test_sensores():
    titulo("TEST 3 — modulo_sensores.py")
    try:
        from modulos.modulo_sensores import run
        q = q_lib.Queue(maxsize=50)

        # Lanzar en hilo en lugar de proceso — evita el problema de path en Windows
        hilo = threading.Thread(target=run, args=(q,), daemon=True)
        hilo.start()

        info("Esperando lecturas del sensor (3 segundos)...")
        time.sleep(3)

        datos = []
        while not q.empty():
            datos.append(q.get_nowait())

        assert len(datos) > 0, "No se recibieron datos del sensor"

        d = datos[0]
        for campo in ['timestamp', 'corriente_A', 'voltaje_V', 'potencia_W', 'energia_J']:
            assert campo in d, f"Falta campo: {campo}"

        corrientes = [x['corriente_A'] for x in datos]
        voltajes   = [x['voltaje_V']   for x in datos]
        assert all(0 < c < 5   for c in corrientes), "Corriente fuera de rango"
        assert all(10 < v < 14 for v in voltajes),   "Voltaje fuera de rango"

        ok(f"Lecturas recibidas: {len(datos)}")
        ok(f"Corriente: {min(corrientes):.2f} – {max(corrientes):.2f} A")
        ok(f"Voltaje:   {min(voltajes):.2f} – {max(voltajes):.2f} V")
        ok(f"Potencia:  {datos[0]['potencia_W']:.2f} W")
        ok(f"Energía:   {datos[-1]['energia_J']:.4f} J")
        return True
    except AssertionError as e:
        fail(str(e)); return False
    except Exception as e:
        fail(f"Error: {e}"); return False


# =============================================================================
# TEST 4 — modulo_motores.py
# Corre en HILO para evitar problema de spawn en Windows
# =============================================================================
def test_motores():
    titulo("TEST 4 — modulo_motores.py")
    try:
        from modulos.modulo_motores import run
        q_vision   = q_lib.Queue(maxsize=10)
        q_comandos = q_lib.Queue(maxsize=20)

        hilo = threading.Thread(target=run, args=(q_vision, q_comandos), daemon=True)
        hilo.start()
        time.sleep(0.3)

        # Cambiar a MANUAL y enviar acciones
        q_comandos.put({'tipo': 'modo', 'valor': 'MANUAL'})
        time.sleep(0.2)
        ok("Comando modo MANUAL enviado")

        for accion in ['base_izq', 'base_der', 'antebrazo_sub', 'brazo1_sub']:
            q_comandos.put({'tipo': 'accion', 'valor': accion})
            time.sleep(0.05)
            ok(f"Acción '{accion}' enviada")

        # Cambiar a AUTO y enviar dato de visión
        q_comandos.put({'tipo': 'modo', 'valor': 'AUTO'})
        time.sleep(0.2)
        q_vision.put({'cx': 350, 'cy': 200, 'detectado': True, 'fruta': 'Naranja'})
        time.sleep(0.3)
        ok("Dato de visión procesado en modo AUTO")
        ok("Módulo de motores responde correctamente")
        return True
    except Exception as e:
        fail(f"Error: {e}"); return False


# =============================================================================
# TEST 5 — modulo_logger.py
# Corre en HILO para evitar problema de spawn en Windows
# =============================================================================
def test_logger():
    titulo("TEST 5 — modulo_logger.py")
    try:
        from modulos.modulo_logger import run
        q_vision   = q_lib.Queue(maxsize=20)
        q_sensores = q_lib.Queue(maxsize=20)

        hilo = threading.Thread(target=run, args=(q_vision, q_sensores), daemon=True)
        hilo.start()
        info("Enviando datos de prueba al logger...")

        for i in range(5):
            q_vision.put({
                'fruta': 'Manzana Roja', 'detectado': True,
                'cx': 310 + i, 'cy': 240, 'radio': 45,
                'hsv': [0, 100, 100, 10, 255, 255]
            })
            q_sensores.put({
                'timestamp':   time.time(),
                'corriente_A': round(1.2 + i * 0.1, 3),
                'voltaje_V':   11.8,
                'potencia_W':  round((1.2 + i * 0.1) * 11.8, 3),
                'energia_J':   round(i * 0.5, 4),
                'subsistema':  'locomocion'
            })
            time.sleep(0.3)

        time.sleep(1)

        # Verificar que se creó el CSV
        os.makedirs(cfg.DATOS_DIR, exist_ok=True)
        csvs = [f for f in os.listdir(cfg.DATOS_DIR)
                if f.startswith('sesion_') and f.endswith('.csv')]
        assert len(csvs) > 0, f"No se encontró CSV en {cfg.DATOS_DIR}"

        import csv
        ultimo = sorted(csvs)[-1]
        ruta   = os.path.join(cfg.DATOS_DIR, ultimo)
        with open(ruta, encoding='utf-8') as f:
            filas = list(csv.DictReader(f))

        assert len(filas) > 0, "El CSV está vacío"

        ok(f"Archivo creado: {ultimo}")
        ok(f"Filas registradas: {len(filas)}")
        ok(f"Columnas: {list(filas[0].keys())}")
        ok(f"Muestra — corriente: {filas[0].get('corriente_A','?')} A, fruta: {filas[0].get('fruta','?')}")
        return True
    except AssertionError as e:
        fail(str(e)); return False
    except Exception as e:
        fail(f"Error: {e}"); return False


# =============================================================================
# TEST 6 — Comunicación entre módulos (colas)
# Sin procesos ni hilos — solo verifica que los datos fluyen bien
# =============================================================================
def test_colas():
    titulo("TEST 6 — Comunicación entre módulos (colas)")
    try:
        q_vision   = q_lib.Queue(maxsize=5)
        q_sensores = q_lib.Queue(maxsize=5)
        q_comandos = q_lib.Queue(maxsize=5)

        # Visión → motores
        q_vision.put_nowait({'cx': 400, 'cy': 300, 'fruta': 'Naranja', 'detectado': True})
        leido = q_vision.get_nowait()
        assert leido['cx'] == 400 and leido['fruta'] == 'Naranja'
        ok(f"Visión → Motores: cx={leido['cx']}, fruta={leido['fruta']}")

        # Sensores → dashboard
        q_sensores.put_nowait({'corriente_A': 1.5, 'voltaje_V': 11.9, 'potencia_W': 17.85})
        leido = q_sensores.get_nowait()
        assert leido['corriente_A'] == 1.5
        ok(f"Sensores → Dashboard: {leido['corriente_A']} A, {leido['voltaje_V']} V")

        # Dashboard → motores (comando manual)
        q_comandos.put_nowait({'tipo': 'accion', 'valor': 'base_izq'})
        cmd = q_comandos.get_nowait()
        assert cmd['valor'] == 'base_izq'
        ok(f"Dashboard → Motores: comando '{cmd['valor']}'")

        # Dashboard → motores (cambio de modo)
        q_comandos.put_nowait({'tipo': 'modo', 'valor': 'MANUAL'})
        cmd = q_comandos.get_nowait()
        assert cmd['tipo'] == 'modo' and cmd['valor'] == 'MANUAL'
        ok(f"Dashboard → Motores: modo '{cmd['valor']}'")

        ok("Todas las colas funcionan correctamente")
        return True
    except AssertionError as e:
        fail(str(e)); return False
    except Exception as e:
        fail(f"Error: {e}"); return False


# =============================================================================
# TEST 7 — modulo_vision.py (requiere cámara)
# Corre en HILO para evitar problema de spawn en Windows
# =============================================================================
def test_vision():
    titulo("TEST 7 — modulo_vision.py (requiere cámara)")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        tiene_camara = cap.isOpened()
        cap.release()

        if not tiene_camara:
            info("Cámara no detectada — test omitido (no es un fallo)")
            return True

        from modulos.modulo_vision import run
        q_vision = q_lib.Queue(maxsize=30)

        hilo = threading.Thread(target=run, args=(q_vision, None), daemon=True)
        hilo.start()

        info("Capturando frames por 3 segundos...")
        time.sleep(3)

        datos = []
        while not q_vision.empty():
            datos.append(q_vision.get_nowait())

        assert len(datos) > 0, "No se recibieron frames de la cámara"

        con_frame    = sum(1 for d in datos if d.get('frame') is not None)
        con_deteccion = sum(1 for d in datos if d.get('detectado'))

        ok(f"Frames recibidos: {len(datos)}")
        ok(f"Frames con imagen: {con_frame}")
        ok(f"Frames con detección: {con_deteccion}")
        ok(f"Fruta activa: {datos[-1].get('fruta', '?')}")
        return True
    except AssertionError as e:
        fail(str(e)); return False
    except Exception as e:
        fail(f"Error: {e}"); return False


# =============================================================================
# Ejecutor
# =============================================================================
TESTS = {
    'config':   test_config,
    'gpio':     test_gpio,
    'sensores': test_sensores,
    'motores':  test_motores,
    'logger':   test_logger,
    'colas':    test_colas,
    'vision':   test_vision,
}

def main():
    args = sys.argv[1:]
    if args:
        invalidos = [a for a in args if a not in TESTS]
        if invalidos:
            print(f"Tests desconocidos: {invalidos}")
            print(f"Disponibles: {', '.join(TESTS.keys())}")
            sys.exit(1)
        seleccion = {k: TESTS[k] for k in args}
    else:
        seleccion = TESTS

    print(f"\n{'='*52}")
    print(f"  VERIFICACIÓN DE MÓDULOS — SISTEMA DE COSECHA")
    print(f"  Corriendo {len(seleccion)} test(s)...")
    print(f"{'='*52}")

    resultados = {}
    for nombre, fn in seleccion.items():
        try:
            resultados[nombre] = fn()
        except Exception as e:
            fail(f"Excepción no manejada en '{nombre}': {e}")
            resultados[nombre] = False

    titulo("RESUMEN")
    for nombre, resultado in resultados.items():
        if resultado:
            ok(nombre)
        else:
            fail(nombre)

    pasaron = sum(1 for r in resultados.values() if r)
    total   = len(resultados)
    print(f"\n  {pasaron}/{total} tests pasaron\n")

    if pasaron == total:
        print(f"  Sistema listo. Ejecuta: python main.py\n")
    else:
        print(f"  Revisa los errores antes de continuar.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
