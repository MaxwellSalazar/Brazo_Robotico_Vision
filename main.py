# =============================================================================
# main.py — Orquestador del sistema de cosecha robótica
#
# EJECUCIÓN:
#   - Procesos del robot: motores, visión, sensores, logger
#   - Dashboard: Streamlit como subproceso (python -m streamlit run ...)
#
# IPC:
#   - Sin dashboard: colas locales (mp.Queue)
#   - Con dashboard: BaseManager con colas expuestas por socket local para que
#     Streamlit y el robot compartan colas reales (ver modulos/bus_manager.py)
#
# Uso:
#   python main.py                     # sistema completo con dashboard
#   python main.py --sin-dashboard     # solo robot, sin Streamlit
#   ROBOT_PLATAFORMA=PI python main.py # modo Raspberry Pi real
# =============================================================================

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional


# Fix Windows multiprocessing 'spawn': agregar raíz del proyecto al path.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


from modulos.modulo_logger import run as run_logger
from modulos.modulo_motores import run as run_motores
from modulos.modulo_sensores import run as run_sensores
from modulos.modulo_vision import run as run_vision


def crear_colas_local() -> Dict[str, Any]:
    return {
        "vision": mp.Queue(maxsize=5),
        "sensores": mp.Queue(maxsize=10),
        "comandos": mp.Queue(maxsize=20),
        "config_vision": mp.Queue(maxsize=5),
    }


def lanzar_procesos(colas: Dict[str, Any]) -> List[mp.Process]:
    procesos = [
        mp.Process(
            target=run_motores,
            args=(colas["vision"], colas["comandos"]),
            name="Motores",
            daemon=True,
        ),
        mp.Process(
            target=run_vision,
            args=(colas["vision"], colas["config_vision"]),
            name="Vision",
            daemon=True,
        ),
        mp.Process(
            target=run_sensores,
            args=(colas["sensores"],),
            name="Sensores",
            daemon=True,
        ),
        mp.Process(
            target=run_logger,
            args=(colas["vision"], colas["sensores"]),
            name="Logger",
            daemon=True,
        ),
    ]
    for p in procesos:
        p.start()
        print(f"  [MAIN] '{p.name}' iniciado — PID {p.pid}")
    return procesos


def hilo_monitor(procesos: List[mp.Process]) -> None:
    """
    Monitor simple: reporta si un proceso cayó.
    (No reinicia: mp.Process no se puede start() dos veces.)
    """
    ya_reportados = set()
    while True:
        time.sleep(5)
        for p in procesos:
            if not p.is_alive() and p.pid not in ya_reportados:
                ya_reportados.add(p.pid)
                print(f"[MAIN] WARN: '{p.name}' caído (exit={p.exitcode}).")


def apagado_limpio(
    procesos: List[mp.Process],
    proc_streamlit: Optional[subprocess.Popen] = None,
    bus_manager: Any = None,
) -> None:
    print("\n[MAIN] Apagando sistema...")

    if proc_streamlit and proc_streamlit.poll() is None:
        proc_streamlit.terminate()
        print("  [MAIN] Dashboard detenido")

    for p in procesos:
        if p.is_alive():
            p.terminate()
            print(f"  [MAIN] '{p.name}' terminado")

    for p in procesos:
        p.join(timeout=3)

    if bus_manager is not None:
        try:
            bus_manager.shutdown()
        except Exception:
            pass

    print("[MAIN] Sistema apagado correctamente.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sistema de cosecha robótica")
    parser.add_argument(
        "--sin-dashboard",
        action="store_true",
        help="Correr solo el robot, sin dashboard",
    )
    args = parser.parse_args()

    print("=" * 52)
    print("  SISTEMA DE COSECHA ROBÓTICA")
    print("=" * 52)

    bus_manager = None
    bus_env: Optional[Dict[str, str]] = None

    if args.sin_dashboard:
        print("[MAIN] Usando colas locales (sin dashboard)...")
        colas = crear_colas_local()
    else:
        print("[MAIN] Iniciando bus IPC para dashboard...")
        from modulos.bus_manager import start_bus_server

        bus_manager, colas, bus_env = start_bus_server()
        print(f"[MAIN] Bus listo en {bus_env['ROBOT_BUS_HOST']}:{bus_env['ROBOT_BUS_PORT']}")

    print("[MAIN] Lanzando módulos:")
    procesos = lanzar_procesos(colas)

    monitor = threading.Thread(target=hilo_monitor, args=(procesos,), daemon=True)
    monitor.start()

    proc_streamlit: Optional[subprocess.Popen] = None

    def _apagar(sig, frame):
        apagado_limpio(procesos, proc_streamlit, bus_manager)
        sys.exit(0)

    signal.signal(signal.SIGINT, _apagar)
    try:
        signal.signal(signal.SIGTERM, _apagar)
    except Exception:
        pass

    print("=" * 52)

    if args.sin_dashboard:
        print("  Modo sin dashboard. Ctrl+C para apagar.\n")
        while True:
            time.sleep(1)
    else:
        print("  Abriendo dashboard en http://localhost:8501")
        print("  Ctrl+C para apagar todo.\n")

        env = os.environ.copy()
        if bus_env:
            env.update(bus_env)

        proc_streamlit = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                os.path.join("modulos", "modulo_dashboard.py"),
                "--server.headless",
                "true",
                "--server.port",
                "8501",
                "--server.fileWatcherType",
                "none",
            ],
            env=env,
        )

        try:
            proc_streamlit.wait()
        finally:
            apagado_limpio(procesos, proc_streamlit, bus_manager)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
