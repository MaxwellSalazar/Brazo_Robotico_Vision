# =============================================================================
# gpio_wrapper.py
# Detecta automáticamente si estamos en Raspberry Pi o en PC.
# Los módulos importan GPIO desde aquí — nunca directamente de RPi.GPIO.
# Así el mismo código corre en desarrollo (Windows/Linux) y en producción (Pi).
# =============================================================================

from config import PLATAFORMA


class _MockGPIO:
    """GPIO simulado para desarrollo en PC. No toca ningún pin real."""
    BCM  = "BCM"
    OUT  = "OUT"
    LOW  = 0
    HIGH = 1

    def setmode(self, mode):
        pass

    def setup(self, pin, mode):
        pass

    def output(self, pin, state):
        # Descomenta la línea siguiente para ver cada pulso en consola:
        # print(f"  [MockGPIO] pin={pin} state={state}")
        pass

    def cleanup(self, pins=None):
        print("[MockGPIO] cleanup() llamado — OK")


def get_gpio():
    """
    Retorna el módulo GPIO correcto según la plataforma configurada.
    Uso:
        from gpio_wrapper import get_gpio
        GPIO = get_gpio()
    """
    if PLATAFORMA == "PI":
        try:
            import RPi.GPIO as GPIO
            return GPIO
        except ImportError:
            print("[WARN] RPi.GPIO no encontrado — usando MockGPIO")
            return _MockGPIO()
    else:
        return _MockGPIO()
