"""
modulos/bus.py

Acceso al bus de colas compartidas entre el robot y el dashboard.

Nota importante:
  No se puede "inyectar" COLAS desde main.py a Streamlit escribiendo una
  variable global de módulo, porque Streamlit corre en OTRO proceso y vuelve
  a importar el módulo desde cero. Para IPC real se usa un BaseManager
  (ver modulos/bus_manager.py).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from modulos.bus_manager import connect_bus_from_env


def get_colas() -> Optional[Dict[str, Any]]:
    """Retorna colas conectadas (si existen vars de entorno) o None."""
    return connect_bus_from_env(os.environ)


# Compatibilidad con imports antiguos (ya no se usa como "canal" de memoria).
COLAS: Dict[str, Any] = {
    "vision": None,
    "sensores": None,
    "comandos": None,
    "config_vision": None,
}

