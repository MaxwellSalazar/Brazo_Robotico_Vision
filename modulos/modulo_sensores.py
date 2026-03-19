# =============================================================================
# modulos/modulo_sensores.py
# Responsabilidad ÚNICA: leer variables eléctricas y publicarlas.
#
# FUENTE ORIGINAL: NO existía en los scripts anteriores.
# Este módulo es NUEVO — corresponde a la fase 2 del proyecto.
#
# En desarrollo (MOCK): genera datos simulados con ruido realista.
# En producción (PI):   lee ADC real (ADS1115 o similar vía I2C).
#
# Publica en q_sensores:
#   {
#     "timestamp":   float,  # time.time()
#     "corriente_A": float,  # amperios — subsistema locomoción
#     "voltaje_V":   float,  # voltios
#     "potencia_W":  float,  # calculada: V × I
#     "energia_J":   float,  # acumulada desde inicio
#     "subsistema":  str     # "locomocion" | "manipulador"
#   }
#
# NO conoce motores, visión ni dashboard.
# =============================================================================

import time
import math
import queue
import random

from config import (
    PLATAFORMA, SENSOR_FREQ_HZ,
    ADC_CANAL_CORRIENTE, ADC_CANAL_VOLTAJE, VOLTAJE_NOMINAL
)


# ---------------------------------------------------------------------------
# Lector MOCK — simula señales realistas para desarrollo en PC
# ---------------------------------------------------------------------------

class _SensorMock:
    """
    Genera corriente y voltaje simulados con variación senoidal + ruido,
    imitando el comportamiento de un motor DC bajo carga variable.
    """
    def __init__(self):
        self._t0 = time.time()

    def leer_corriente(self):
        t = time.time() - self._t0
        # Corriente base 1.2A + variación senoidal + ruido pequeño
        return round(1.2 + 0.4 * math.sin(t * 0.8) + random.gauss(0, 0.05), 3)

    def leer_voltaje(self):
        t = time.time() - self._t0
        # Voltaje cae ligeramente bajo carga
        return round(VOLTAJE_NOMINAL - 0.3 * abs(math.sin(t * 0.4))
                     + random.gauss(0, 0.02), 3)


# ---------------------------------------------------------------------------
# Lector REAL — usa ADS1115 via I2C (solo Raspberry Pi)
# ---------------------------------------------------------------------------

class _SensorReal:
    """
    Lee el ADC externo ADS1115.
    Requiere: pip install adafruit-circuitpython-ads1x15
    """
    def __init__(self):
        import board
        import busio
        import adafruit_ads1x15.ads1115 as ADS
        from adafruit_ads1x15.analog_in import AnalogIn

        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)

        self._canal_i = AnalogIn(ads, ADC_CANAL_CORRIENTE)
        self._canal_v = AnalogIn(ads, ADC_CANAL_VOLTAJE)

        # Factor de conversión del sensor de corriente (ACS712 5A → 185 mV/A)
        self._mv_por_amp = 0.185
        self._v_ref      = 2.5     # voltaje de referencia del sensor

    def leer_corriente(self):
        voltaje_sensor = self._canal_i.voltage
        corriente = (voltaje_sensor - self._v_ref) / self._mv_por_amp
        return round(corriente, 3)

    def leer_voltaje(self):
        # Divisor resistivo: ajustar factor según tu circuito
        return round(self._canal_v.voltage * 4.0, 3)


# ---------------------------------------------------------------------------
# Punto de entrada llamado por main.py
# ---------------------------------------------------------------------------

def run(q_sensores):
    """
    Proceso independiente de sensores.
    Lee variables eléctricas a SENSOR_FREQ_HZ Hz y las publica en q_sensores.
    """
    print(f"[SENSORES] Módulo iniciado (plataforma: {PLATAFORMA})")

    if PLATAFORMA == "PI":
        try:
            sensor = _SensorReal()
            print("[SENSORES] ADC real inicializado")
        except Exception as e:
            print(f"[SENSORES] WARN: ADC real falló ({e}) — usando Mock")
            sensor = _SensorMock()
    else:
        sensor = _SensorMock()
        print("[SENSORES] Usando sensor simulado")

    intervalo  = 1.0 / SENSOR_FREQ_HZ
    energia_J  = 0.0
    t_anterior = time.time()

    try:
        while True:
            t_ahora    = time.time()
            dt         = t_ahora - t_anterior
            t_anterior = t_ahora

            corriente = sensor.leer_corriente()
            voltaje   = sensor.leer_voltaje()
            potencia  = round(corriente * voltaje, 3)
            energia_J = round(energia_J + potencia * dt, 4)

            dato = {
                "timestamp":   t_ahora,
                "corriente_A": corriente,
                "voltaje_V":   voltaje,
                "potencia_W":  potencia,
                "energia_J":   energia_J,
                "subsistema":  "locomocion",   # se expandirá en fase 2
            }

            try:
                q_sensores.put_nowait(dato)
            except queue.Full:
                pass

            time.sleep(intervalo)

    except KeyboardInterrupt:
        pass
    finally:
        print(f"[SENSORES] Energía total registrada: {energia_J:.4f} J")
        print("[SENSORES] Módulo detenido")
