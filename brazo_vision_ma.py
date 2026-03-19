import cv2
import numpy as np
import RPi.GPIO as GPIO
import time

# ------------------ DISPLAY ------------------
DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480

CAM_W = 520     # zona izquierda cámara
PANEL_W = 280   # zona derecha sliders

# ------------------ MOTORES ------------------
MOTORES = {
    'base': {'DIR':9,'STEP':10,'avance':0},
    'brazo_1': {'DIR':21,'STEP':20,'avance':0},
    'brazo_2': {'DIR':7,'STEP':8,'avance':0},
    'antebrazo': {'DIR':6,'STEP':5,'avance':0}
}

estado_motores={k:'Detenido' for k in MOTORES}
modo="AUTO"
tecla_activa=None

GPIO.setmode(GPIO.BCM)
for m in MOTORES.values():
    GPIO.setup(m['DIR'],GPIO.OUT)
    GPIO.setup(m['STEP'],GPIO.OUT)

# ------------------ CONTROL MOTORES ------------------
def mover_motor(nombre,direccion,pasos,delay=0.0008):
    motor=MOTORES[nombre]
    GPIO.output(motor['DIR'],direccion)
    estado_motores[nombre]='Arriba' if direccion else 'Abajo'
    for _ in range(pasos):
        GPIO.output(motor['STEP'],1)
        time.sleep(delay)
        GPIO.output(motor['STEP'],0)
        time.sleep(delay)

# ------------------ HSV BASE (EDITABLE CON SLIDER) ------------------
HSV_PRESETS={
"Manzana Roja":[0,100,100,10,255,255],
"Manzana Verde":[35,100,100,85,255,255],
"Naranja":[10,100,100,25,255,255],
"Limon":[25,100,100,35,255,255]
}

# sliders
def nothing(x): pass

cv2.namedWindow("Resultado",cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty("Resultado",cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)

cv2.createTrackbar("H min","Resultado",0,179,nothing)
cv2.createTrackbar("S min","Resultado",0,255,nothing)
cv2.createTrackbar("V min","Resultado",0,255,nothing)
cv2.createTrackbar("H max","Resultado",179,179,nothing)
cv2.createTrackbar("S max","Resultado",255,255,nothing)
cv2.createTrackbar("V max","Resultado",255,255,nothing)

def set_sliders(vals):
    cv2.setTrackbarPos("H min","Resultado",vals[0])
    cv2.setTrackbarPos("S min","Resultado",vals[1])
    cv2.setTrackbarPos("V min","Resultado",vals[2])
    cv2.setTrackbarPos("H max","Resultado",vals[3])
    cv2.setTrackbarPos("S max","Resultado",vals[4])
    cv2.setTrackbarPos("V max","Resultado",vals[5])

def leer_sliders():
    return [
        cv2.getTrackbarPos("H min","Resultado"),
        cv2.getTrackbarPos("S min","Resultado"),
        cv2.getTrackbarPos("V min","Resultado"),
        cv2.getTrackbarPos("H max","Resultado"),
        cv2.getTrackbarPos("S max","Resultado"),
        cv2.getTrackbarPos("V max","Resultado")
    ]

# ------------------ VISIÓN ------------------
def reconocer_fruta(img):

    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    hmin,smin,vmin,hmax,smax,vmax=leer_sliders()

    lower=np.array([hmin,smin,vmin])
    upper=np.array([hmax,smax,vmax])

    mask=cv2.inRange(hsv,lower,upper)
    contornos,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

    if contornos:
        c=max(contornos,key=cv2.contourArea)
        if cv2.contourArea(c)>600:
            (x,y),r=cv2.minEnclosingCircle(c)
            return img,(int(x),int(y)),int(r)

    return img,None,None

# ------------------ AUTOMÁTICO ------------------
def alinear(cx,cy,margen=50):
    centro_x,centro_y=320,240
    dx=cx-centro_x
    dy=cy-centro_y

    if abs(dx)>margen:
        mover_motor('base',GPIO.LOW if dx>0 else GPIO.HIGH,int(abs(dx)*0.2))

    if abs(dy)>margen:
        mover_motor('antebrazo',GPIO.HIGH if dy<0 else GPIO.LOW,int(abs(dy)*0.2))

# ------------------ MANUAL ------------------
def control_manual(key):
    pasos=40

    if key==ord('a'): mover_motor('base',GPIO.LOW,pasos)
    if key==ord('d'): mover_motor('base',GPIO.HIGH,pasos)
    if key==ord('w'): mover_motor('antebrazo',GPIO.HIGH,pasos)
    if key==ord('s'): mover_motor('antebrazo',GPIO.LOW,pasos)
    if key==ord('i'): mover_motor('brazo_1',GPIO.HIGH,pasos)
    if key==ord('k'): mover_motor('brazo_1',GPIO.LOW,pasos)
    if key==ord('j'): mover_motor('brazo_2',GPIO.HIGH,pasos)
    if key==ord('l'): mover_motor('brazo_2',GPIO.LOW,pasos)

# ------------------ CAMARA ------------------
cap=cv2.VideoCapture(0)
cap.set(3,640)
cap.set(4,480)

fruta_actual="Manzana Roja"
set_sliders(HSV_PRESETS[fruta_actual])

mapa={
ord('1'):"Manzana Roja",
ord('2'):"Manzana Verde",
ord('3'):"Naranja",
ord('4'):"Limon"
}

print("MODO AUTOMÁTICO | Presiona M para cambiar a MANUAL")

# ------------------ LOOP ------------------
try:
    while True:

        ret,frame=cap.read()
        if not ret: break

        key=cv2.waitKey(30)&0xFF
        if key!=255: tecla_activa=key

        if key==ord('m'):
            modo="MANUAL" if modo=="AUTO" else "AUTO"
            time.sleep(0.3)

        if key in mapa:
            fruta_actual=mapa[key]
            set_sliders(HSV_PRESETS[fruta_actual])
            print("Fruta:",fruta_actual,"HSV:",leer_sliders())

        if key==ord('q'): break

        frame,centro,r=reconocer_fruta(frame)

        if centro:
            cv2.circle(frame,centro,r,(0,255,0),2)
            if modo=="AUTO":
                alinear(centro[0],centro[1])

        if modo=="MANUAL" and tecla_activa:
            control_manual(tecla_activa)

        # ================= PANEL UI =================
        cam=cv2.resize(frame,(CAM_W,DISPLAY_HEIGHT))

        panel=np.zeros((DISPLAY_HEIGHT,PANEL_W,3),dtype=np.uint8)

        y=40
        cv2.putText(panel,"HSV CONTROL",(20,y),
                    cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)
        y+=60

        nombres=["Hmin","Smin","Vmin","Hmax","Smax","Vmax"]
        valores=leer_sliders()

        for n,v in zip(nombres,valores):
            cv2.putText(panel,f"{n}: {v}",(20,y),
                        cv2.FONT_HERSHEY_SIMPLEX,0.7,(255,255,255),2)
            y+=45

        cv2.putText(panel,f"Modo: {modo}",(20,DISPLAY_HEIGHT-100),
                    cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,255),2)

        cv2.putText(panel,fruta_actual,(20,DISPLAY_HEIGHT-60),
                    cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,255,0),2)

        salida=np.hstack((cam,panel))
        cv2.imshow("Resultado",salida)

finally:
    cap.release()
    cv2.destroyAllWindows()
    GPIO.cleanup()