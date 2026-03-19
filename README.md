# Sistema de Cosecha Robótica — Arquitectura Modular (preliminar)

Este repositorio es una **versión preliminar** de un proyecto de **brazo robótico cosechador por visión artificial**, con **dashboard** para monitoreo y control. Está pensado para poder **probarse en PC sin Raspberry Pi** (modo `MOCK`).

## Estructura del proyecto

```
.
│
├── main.py              ← Punto de entrada del sistema (robot + dashboard)
├── config.py            ← Parámetros globales (pines, HSV, frecuencias)
├── gpio_wrapper.py      ← Abstracción GPIO: Pi vs PC (Mock)
├── test_modulos.py      ← Pruebas rápidas por módulo (PC / Pi)
│
├── modulos/
│   ├── bus_manager.py        ← IPC real (colas) para Streamlit ↔ robot
│   ├── bus.py                ← Conexión al bus desde variables de entorno
│   ├── modulo_motores.py     ← Control GPIO de motores stepper
│   ├── modulo_vision.py      ← OpenCV: captura y detección de fruta por HSV
│   ├── modulo_sensores.py    ← Sensores eléctricos (Mock en PC / ADC en Pi)
│   ├── modulo_logger.py      ← Registro CSV por sesión
│   └── modulo_dashboard.py   ← Dashboard Streamlit
│
├── datos/               ← CSVs generados por sesión (auto)
│   └── sesion_YYYY-MM-DD_HH-MM-SS.csv
│
├── requirements.txt
└── requirements-pi.txt
```

## Scripts anteriores (ya no se usan)

| Script original      | Reemplazado por                                          |
|----------------------|----------------------------------------------------------|
| `control_robot.py`   | `modulos/modulo_motores.py` + `modulos/modulo_vision.py` |
| `dashboard_robot.py` | `modulos/modulo_dashboard.py`                            |

Puedes guardarlos en una carpeta `archivo/` como referencia histórica, pero ya no participan en el sistema modular.

## Cómo ejecutar

### Paso 0 — Verificar módulos (recomendado)

```bash
python test_modulos.py
```

### En PC (desarrollo, sin hardware Raspberry)

```bash
pip install -r requirements.txt

# Sistema completo: robot + dashboard
python main.py
# → abre http://localhost:8501

# Solo robot, sin dashboard
python main.py --sin-dashboard

# Solo dashboard (UI sin robot)
streamlit run modulos/modulo_dashboard.py
# → muestra banner de "Modo desarrollo" y sensores simulados
```

Notas:
- `gpio_wrapper.py` usa GPIO simulado en PC (`PLATAFORMA=MOCK`).
- `modulos/modulo_sensores.py` simula lecturas en PC.
- `modulos/modulo_vision.py` requiere cámara (USB/webcam). Si no hay cámara, el módulo de visión avisa y se detiene; el resto del sistema puede seguir corriendo.

## Flujo recomendado (Laptop → Raspberry) y colaboración

Para programar y probar primero en tu laptop, y luego “cargar” a la Raspberry cuando tengas acceso (y además colaborar con otros), lo más práctico es usar **Git**:

1) En tu laptop: trabajas normalmente (modo `MOCK`), haces commits y subes a un repo remoto (GitHub/GitLab).
2) En la Raspberry: cuando la tengas disponible, haces `git pull` y ejecutas en modo `PI`.

Esto evita copiar archivos a mano y permite colaborar con ramas y Pull Requests.

### En Raspberry Pi (producción)

```bash
pip install -r requirements-pi.txt

export ROBOT_PLATAFORMA=PI
python main.py
```

### Actualizar el código en la Raspberry (cuando tengas acceso)

Dentro de la carpeta del proyecto en la Pi:

```bash
git pull
source .venv/bin/activate
pip install -r requirements-pi.txt
export ROBOT_PLATAFORMA=PI
python test_modulos.py
python main.py
```

## Comunicación entre módulos (colas)

Cada módulo corre en un proceso independiente. Se comunican exclusivamente con colas.

- **Sin dashboard**: colas locales (`multiprocessing.Queue`).
- **Con dashboard**: `main.py` inicia un **bus IPC** con `BaseManager` (socket local) para que el subproceso de Streamlit pueda conectarse a las colas reales.

Flujo lógico:

```
[Cámara USB] → modulo_vision.py  ─── q_vision ───→ modulo_motores.py (AUTO)
                              └─── q_vision ───→ modulo_logger.py
                              └─── q_vision ───→ modulo_dashboard.py

[ADC / Mock] → modulo_sensores.py ─ q_sensores ─→ modulo_logger.py
                               └── q_sensores ─→ modulo_dashboard.py

modulo_dashboard.py ─── q_comandos ─→ modulo_motores.py (MANUAL)
                   └── q_config_vision → modulo_vision.py (preset/HSV)
```

## Estado de módulos

| Archivo                     | Estado     |
|----------------------------|------------|
| `main.py`                  | Completo   |
| `config.py`                | Completo   |
| `gpio_wrapper.py`          | Completo   |
| `test_modulos.py`          | Completo   |
| `modulos/bus_manager.py`   | Completo   |
| `modulos/modulo_motores.py`| Completo   |
| `modulos/modulo_vision.py` | Completo   |
| `modulos/modulo_sensores.py`| Completo* |
| `modulos/modulo_logger.py` | Completo   |
| `modulos/modulo_dashboard.py`| Completo |
| `modulos/modulo_ia.py`     | Pendiente  |

\*`modulo_sensores.py` incluye simulación para PC. En Pi intenta inicializar ADC real.

## Modos del dashboard

| Cómo se lanza                             | Modo        | Comportamiento |
|-------------------------------------------|-------------|----------------|
| `python main.py`                          | Integrado   | Conecta a colas reales vía IPC |
| `streamlit run modulos/modulo_dashboard.py` | Desarrollo | Sensores simulados, sin robot |

## Agregar módulo de IA (fase futura)

Cuando llegue el momento:

1. Crear `modulos/modulo_ia.py` con una función `run(q_vision, q_decision)`
2. Agregar una cola `decision` en `main.py`
3. Lanzar el proceso IA desde `main.py`
4. Suscribir `modulos/modulo_motores.py` a `q_decision`

El resto del sistema no debería cambiar.
