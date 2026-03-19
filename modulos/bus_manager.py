"""
modulos/bus_manager.py

Bus IPC para que el dashboard (Streamlit) y el orquestador (main.py) compartan
colas reales aun siendo procesos distintos.

En lugar de intentar "compartir" variables de un módulo (lo cual NO funciona
entre procesos), se levanta un BaseManager que expone 4 colas:
  - vision
  - sensores
  - comandos
  - config_vision

main.py inicia el servidor y pasa los datos de conexión al subproceso de
Streamlit vía variables de entorno:
  ROBOT_BUS_HOST, ROBOT_BUS_PORT, ROBOT_BUS_AUTH
"""

from __future__ import annotations

import base64
import queue
import secrets
import socket
from multiprocessing.managers import BaseManager
from typing import Any, Dict, Optional, Tuple

_REGISTERED = False
_QUEUES: Dict[str, "queue.Queue[Any]"] = {}


def _init_server(maxsizes: Dict[str, int]) -> None:
    global _QUEUES
    _QUEUES = {
        "vision": queue.Queue(maxsize=maxsizes.get("vision", 5)),
        "sensores": queue.Queue(maxsize=maxsizes.get("sensores", 10)),
        "comandos": queue.Queue(maxsize=maxsizes.get("comandos", 20)),
        "config_vision": queue.Queue(maxsize=maxsizes.get("config_vision", 5)),
    }


def _q_vision():
    return _QUEUES["vision"]


def _q_sensores():
    return _QUEUES["sensores"]


def _q_comandos():
    return _QUEUES["comandos"]


def _q_config_vision():
    return _QUEUES["config_vision"]


class BusManager(BaseManager):
    pass


def _register(server: bool) -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    if server:
        BusManager.register("vision_queue", callable=_q_vision)
        BusManager.register("sensores_queue", callable=_q_sensores)
        BusManager.register("comandos_queue", callable=_q_comandos)
        BusManager.register("config_vision_queue", callable=_q_config_vision)
    else:
        BusManager.register("vision_queue")
        BusManager.register("sensores_queue")
        BusManager.register("comandos_queue")
        BusManager.register("config_vision_queue")

    _REGISTERED = True


def _pick_free_port(host: str) -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, 0))
        return int(s.getsockname()[1])
    finally:
        s.close()


def start_bus_server(
    host: str = "127.0.0.1",
    port: Optional[int] = None,
    authkey: Optional[bytes] = None,
    maxsizes: Optional[Dict[str, int]] = None,
) -> Tuple[BusManager, Dict[str, Any], Dict[str, str]]:
    """
    Inicia el servidor de colas y retorna:
      (manager, colas_proxy, env_dict)

    `env_dict` contiene ROBOT_BUS_HOST/PORT/AUTH para pasarlos a Streamlit.
    """
    if port is None:
        port = _pick_free_port(host)
    if authkey is None:
        authkey = secrets.token_bytes(24)
    if maxsizes is None:
        maxsizes = {"vision": 5, "sensores": 10, "comandos": 20, "config_vision": 5}

    _register(server=True)
    manager = BusManager(address=(host, port), authkey=authkey)
    manager.start(initializer=_init_server, initargs=(maxsizes,))

    colas = {
        "vision": manager.vision_queue(),
        "sensores": manager.sensores_queue(),
        "comandos": manager.comandos_queue(),
        "config_vision": manager.config_vision_queue(),
    }

    auth_b64 = base64.urlsafe_b64encode(authkey).decode("ascii")
    env = {
        "ROBOT_BUS_HOST": host,
        "ROBOT_BUS_PORT": str(port),
        "ROBOT_BUS_AUTH": auth_b64,
    }
    return manager, colas, env


def connect_bus_from_env(environ: Dict[str, str]) -> Optional[Dict[str, Any]]:
    host = environ.get("ROBOT_BUS_HOST")
    port_s = environ.get("ROBOT_BUS_PORT")
    auth_s = environ.get("ROBOT_BUS_AUTH")
    if not host or not port_s or not auth_s:
        return None

    try:
        port = int(port_s)
        authkey = base64.urlsafe_b64decode(auth_s.encode("ascii"))
    except Exception:
        return None

    _register(server=False)
    manager = BusManager(address=(host, port), authkey=authkey)
    manager.connect()

    return {
        "vision": manager.vision_queue(),
        "sensores": manager.sensores_queue(),
        "comandos": manager.comandos_queue(),
        "config_vision": manager.config_vision_queue(),
    }
