# Dashboar interactivo en python
# Ejecución 
# python -m streamlit run dashboard_robot.py
# # =============================================================================
# ESTRUCTURA GENERAL DEL SISTEMA DE COSECHA (DASHBOARD INTERACTIVO)
# =============================================================================
# Este script se divide en 4 capas principales que funcionan en conjunto:
#
# 1. CAPA DE EMULACIÓN (Hardware Mock):
#    Crea una clase "falsa" de GPIO para que el código no falle en Windows. 
#    Cuando se pase a la Raspberry Pi real, solo se debe borrar esta clase 
#    e importar la librería RPi.GPIO auténtica.
#
# 2. INTERFAZ DE USUARIO (Streamlit):
#    Define la disposición visual (layout). Usa una barra lateral para los 
#    controles de color (HSV) y columnas en el centro para separar el video 
#    de los registros de actividad (logs). Es lo que el usuario ve en el navegador.
#
# 3. PROCESAMIENTO DE VISIÓN (OpenCV):
#    Captura el video en tiempo real. Aplica filtros de color basados en los 
#    sliders del dashboard para aislar la fruta. Si detecta un objeto que 
#    supera el tamaño mínimo, dibuja un cuadro y calcula su centro para el brazo.
#
# 4. LÓGICA DE CONTROL (Manual vs. Automático):
#    - MODO AUTO: El sistema compara la posición de la fruta en la imagen 
#      contra el centro de la cámara y genera órdenes de movimiento automáticas.
#    - MODO MANUAL: El usuario toma el control mediante los botones del dashboard.
#    - REGISTRO (Logs): Cada acción queda guardada en una lista temporal para 
#      auditar qué está haciendo el robot en cada segundo.
# =============================================================================

import streamlit as st
import cv2
import numpy as np
import time

# --- MOCK DE GPIO (Para que funcione en Windows sin Raspberry) ---
class MockGPIO:
    BCM = "BCM"
    OUT = "OUT"
    LOW = 0
    HIGH = 1
    def setmode(self, mode): pass
    def setup(self, pin, mode): pass
    def output(self, pin, state): pass
    def cleanup(self): pass

GPIO = MockGPIO()

# --- CONFIGURACIÓN DE PANTALLA ---
st.set_page_config(page_title="Brazo Cosechador Dashboard", layout="wide")

# --- ESTADO INICIAL ---
if 'modo' not in st.session_state:
    st.session_state.modo = "AUTO"
if 'logs' not in st.session_state:
    st.session_state.logs = []

# --- LÓGICA DE MOTORES (SIMULADA) ---
MOTORES = {
    'base': {'DIR':9,'STEP':10},
    'brazo_1': {'DIR':21,'STEP':20},
    'brazo_2': {'DIR':7,'STEP':8},
    'antebrazo': {'DIR':6,'STEP':5}
}

def registrar_movimiento(nombre, direccion):
    dir_txt = "Derecha/Arriba" if direccion == 1 else "Izquierda/Abajo"
    msg = f"[{time.strftime('%H:%M:%S')}] Motor {nombre} movido hacia {dir_txt}"
    st.session_state.logs.insert(0, msg)
    if len(st.session_state.logs) > 5: st.session_state.logs.pop()

# --- SIDEBAR: CONTROLES ---
st.sidebar.title("⚙️ Configuración")
fruta_seleccionada = st.sidebar.selectbox("Seleccionar Fruta", ["Manzana Roja", "Manzana Verde", "Naranja", "Limon"])

st.sidebar.subheader("Ajuste Fino HSV")
h_min = st.sidebar.slider("H min", 0, 179, 0)
s_min = st.sidebar.slider("S min", 0, 255, 100)
v_min = st.sidebar.slider("V min", 0, 255, 100)
h_max = st.sidebar.slider("H max", 0, 179, 10 if fruta_seleccionada == "Manzana Roja" else 179)
s_max = st.sidebar.slider("S max", 0, 255, 255)
v_max = st.sidebar.slider("V max", 0, 255, 255)

# --- CUERPO PRINCIPAL ---
st.title("🚜 Dashboard de Control: Brazo Cosechador")

col_cam, col_info = st.columns([2, 1])

with col_info:
    st.subheader("Estado del Sistema")
    st.toggle("Modo Manual / Auto", key="check_modo")
    st.session_state.modo = "MANUAL" if st.session_state.check_modo else "AUTO"
    st.info(f"Modo actual: **{st.session_state.modo}**")
    
    st.subheader("Telemetría Virtual")
    st.write("Últimos movimientos:")
    for log in st.session_state.logs:
        st.text(log)

    if st.session_state.modo == "MANUAL":
        st.warning("Control Manual Activado")
        c1, c2 = st.columns(2)
        if c1.button("⬅️ Base Izq"): registrar_movimiento('base', 0)
        if c2.button("Base Der ➡️"): registrar_movimiento('base', 1)
        if c1.button("🔼 Brazo Subir"): registrar_movimiento('brazo_1', 1)
        if c2.button("Brazo Bajar 🔽"): registrar_movimiento('brazo_1', 0)

# --- PROCESAMIENTO DE IMAGEN (OpenCV) ---
cap = cv2.VideoCapture(0) # Usa tu webcam de Windows
frame_placeholder = col_cam.empty()

while True:
    ret, frame = cap.read()
    if not ret:
        st.error("No se pudo acceder a la cámara")
        break

    # Convertir a HSV y filtrar
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array([h_min, s_min, v_min])
    upper = np.array([h_max, s_max, v_max])
    mask = cv2.inRange(hsv, lower, upper)
    
    # Encontrar contornos
    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contornos:
        c = max(contornos, key=cv2.contourArea)
        if cv2.contourArea(c) > 1000:
            x, y, w, h = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
            cv2.putText(frame, f"Detectado: {fruta_seleccionada}", (x, y-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # Simulación de alineación en modo AUTO
            if st.session_state.modo == "AUTO":
                centro_x = x + w//2
                if centro_x < 200: registrar_movimiento('base', 0)
                elif centro_x > 440: registrar_movimiento('base', 1)

    # Mostrar en Streamlit
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
    
    # Pequeña pausa para no saturar el procesador
    time.sleep(0.05)