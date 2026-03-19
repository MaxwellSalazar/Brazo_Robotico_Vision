# =============================================================================
# config.py
# Fuente única de verdad para todos los parámetros del sistema.
# NUNCA escribas valores hardcodeados en los módulos — impórtalos desde aquí.
# =============================================================================

import os

# --- GPIO: pines de cada motor (BCM) ---
MOTORES = {
    'base':      {'DIR': 9,  'STEP': 10},
    'brazo_1':   {'DIR': 21, 'STEP': 20},
    'brazo_2':   {'DIR': 7,  'STEP': 8},
    'antebrazo': {'DIR': 6,  'STEP': 5},
}
PASOS_MANUAL  = 40       # pasos por pulsación en modo manual
DELAY_STEP    = 0.0008   # segundos entre pulsos del stepper

# --- Visión artificial ---
CAMARA_ID   = 0
CAM_ANCHO   = 640
CAM_ALTO    = 480
MARGEN_AUTO = 50         # tolerancia en px para alineación automática
AREA_MIN    = 600        # área mínima de contorno para considerar detección válida

HSV_PRESETS = {
    "Manzana Roja":  [0,   100, 100, 10,  255, 255],
    "Manzana Verde": [35,  100, 100, 85,  255, 255],
    "Naranja":       [10,  100, 100, 25,  255, 255],
    "Limon":         [25,  100, 100, 35,  255, 255],
}
FRUTA_DEFAULT = "Manzana Roja"

# --- Sensores eléctricos ---
# (se completará cuando se integre el ADC físico)
ADC_CANAL_CORRIENTE  = 0
ADC_CANAL_VOLTAJE    = 1
SENSOR_FREQ_HZ       = 10    # lecturas por segundo
VOLTAJE_NOMINAL      = 12.0  # V — referencia para alertas

# --- Logger ---
DATOS_DIR    = os.path.join(os.path.dirname(__file__), "datos")
LOG_FREQ_HZ  = 5   # registros por segundo en el CSV

# --- Modo de ejecución ---
# "PI"      → usa RPi.GPIO real (Raspberry Pi)
# "MOCK"    → simula GPIO (desarrollo en PC/Windows)
PLATAFORMA = os.environ.get("ROBOT_PLATAFORMA", "MOCK")
