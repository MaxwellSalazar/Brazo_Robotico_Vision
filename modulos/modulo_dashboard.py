# =============================================================================
# modulos/modulo_dashboard.py
#
# DOS MODOS DE USO:
#
#   A) Solo (desarrollo — sin robot):
#      streamlit run modulos/modulo_dashboard.py
#      → Sin bus IPC. Sensores simulados. Sin video real.
#
#   B) Integrado (desde main.py):
#      python main.py
#      → main.py inicia un bus IPC (BaseManager) y pasa conexión vía ENV.
#        El dashboard se conecta y recibe colas reales.
# =============================================================================

from __future__ import annotations

import multiprocessing as mp
import time

import numpy as np
import streamlit as st

from config import FRUTA_DEFAULT, HSV_PRESETS


def _obtener_colas():
    """Colas reales (main.py) o locales (modo solo)."""
    try:
        from modulos.bus import get_colas

        colas = get_colas()
        if colas is not None:
            return colas, True
    except Exception:
        pass

    return {
        "vision": mp.Queue(maxsize=5),
        "sensores": mp.Queue(maxsize=10),
        "comandos": mp.Queue(maxsize=20),
        "config_vision": mp.Queue(maxsize=5),
    }, False


def _sensor_mock():
    import math

    t = time.time()
    corriente = 1.2 + 0.4 * math.sin(t * 0.8)
    return {
        "corriente_A": round(corriente, 2),
        "voltaje_V": round(11.8 + 0.1 * math.sin(t * 0.3), 2),
        "potencia_W": round(corriente * 11.8, 2),
        "energia_J": round(t % 1000, 2),
    }


def _estado_inicial():
    defaults = {
        "modo": "AUTO",
        "fruta": FRUTA_DEFAULT,
        "ultimo_vision": {},
        "ultimo_sensor": {},
        "frame_actual": None,
        "logs": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _leer_colas(colas, integrado: bool):
    # Visión
    while True:
        try:
            dato = colas["vision"].get_nowait()
            if "frame" in dato:
                st.session_state["frame_actual"] = dato["frame"]
            st.session_state["ultimo_vision"] = {k: v for k, v in dato.items() if k != "frame"}
        except Exception:
            break

    # Sensores
    if integrado:
        while True:
            try:
                st.session_state["ultimo_sensor"] = colas["sensores"].get_nowait()
            except Exception:
                break
    else:
        st.session_state["ultimo_sensor"] = _sensor_mock()


def _log(msg: str):
    st.session_state["logs"].insert(0, f"[{time.strftime('%H:%M:%S')}] {msg}")
    if len(st.session_state["logs"]) > 10:
        st.session_state["logs"].pop()


def _render():
    colas, integrado = _obtener_colas()
    st.set_page_config(page_title="Brazo Cosechador", layout="wide")
    _estado_inicial()
    _leer_colas(colas, integrado)

    if not integrado:
        st.warning(
            "Modo desarrollo — sensores simulados, sin robot ni cámara real. "
            "Ejecuta `python main.py` para el sistema completo."
        )

    # Sidebar
    with st.sidebar:
        st.title("Configuración")
        frutas = list(HSV_PRESETS.keys())
        nueva_fruta = st.selectbox(
            "Fruta objetivo",
            frutas,
            index=frutas.index(st.session_state["fruta"]),
        )
        if nueva_fruta != st.session_state["fruta"]:
            st.session_state["fruta"] = nueva_fruta
            try:
                colas["config_vision"].put_nowait({"fruta": nueva_fruta})
            except Exception:
                pass
            _log(f"Fruta → {nueva_fruta}")

        preset = HSV_PRESETS[st.session_state["fruta"]]
        st.subheader("Ajuste HSV")
        h_min = st.slider("H min", 0, 179, preset[0])
        s_min = st.slider("S min", 0, 255, preset[1])
        v_min = st.slider("V min", 0, 255, preset[2])
        h_max = st.slider("H max", 0, 179, preset[3])
        s_max = st.slider("S max", 0, 255, preset[4])
        v_max = st.slider("V max", 0, 255, preset[5])
        if st.button("Aplicar HSV"):
            try:
                colas["config_vision"].put_nowait({"hsv": [h_min, s_min, v_min, h_max, s_max, v_max]})
            except Exception:
                pass
            _log("HSV actualizado")

    # Cuerpo
    st.title("Dashboard — Brazo Cosechador")
    col_cam, col_info = st.columns([2, 1])

    with col_cam:
        frame = st.session_state.get("frame_actual")
        if frame is not None:
            import cv2

            st.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)
        else:
            st.image(np.zeros((480, 640, 3), dtype=np.uint8), caption="Sin señal de cámara", use_container_width=True)

        v = st.session_state["ultimo_vision"]
        if v.get("detectado"):
            st.success(
                f"Detectado: **{v.get('fruta', '')}** | pos ({v.get('cx', '?')}, {v.get('cy', '?')}) | "
                f"radio {v.get('radio', '?')} px"
            )
        else:
            st.warning("Sin detección en este frame")

    with col_info:
        st.subheader("Control")
        nuevo_modo = "MANUAL" if st.toggle("Modo Manual", value=(st.session_state["modo"] == "MANUAL")) else "AUTO"
        if nuevo_modo != st.session_state["modo"]:
            st.session_state["modo"] = nuevo_modo
            try:
                colas["comandos"].put_nowait({"tipo": "modo", "valor": nuevo_modo})
            except Exception:
                pass
            _log(f"Modo → {nuevo_modo}")

        st.info(f"Modo actual: **{st.session_state['modo']}**")

        s = st.session_state["ultimo_sensor"]
        if s:
            st.subheader("Sensores eléctricos")
            m1, m2, m3 = st.columns(3)
            m1.metric("Corriente", f"{s.get('corriente_A', 0):.2f} A")
            m2.metric("Voltaje", f"{s.get('voltaje_V', 0):.2f} V")
            m3.metric("Potencia", f"{s.get('potencia_W', 0):.2f} W")
            st.caption(f"Energía acumulada: {s.get('energia_J', 0):.3f} J")

        if st.session_state["modo"] == "MANUAL":
            st.subheader("Control manual")

            def cmd(a: str):
                try:
                    colas["comandos"].put_nowait({"tipo": "accion", "valor": a})
                except Exception:
                    pass
                _log(f"CMD → {a}")

            c1, c2 = st.columns(2)
            if c1.button("Base Izq"):
                cmd("base_izq")
            if c2.button("Base Der"):
                cmd("base_der")
            if c1.button("Antebrazo +"):
                cmd("antebrazo_sub")
            if c2.button("Antebrazo −"):
                cmd("antebrazo_baj")
            if c1.button("Brazo 1 +"):
                cmd("brazo1_sub")
            if c2.button("Brazo 1 −"):
                cmd("brazo1_baj")

        st.subheader("Actividad")
        for e in st.session_state["logs"]:
            st.text(e)

    time.sleep(0.2)
    st.rerun()


if __name__ == "__main__":
    _render()
