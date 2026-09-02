# X-BLAST Enterprise v2.0 (PERVOL)

<p align="center">
  <img src="assets/X-BLAST.png" alt="X-BLAST Enterprise Logo" width="220" />
</p>

<p align="center">
  <strong>Plataforma Integral de Simulación, Diseño y Optimización de Perforación y Voladura de Rocas</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue?logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/GUI-PySide6%20(Qt6)-41CD52?logo=qt" alt="GUI PySide6" />
  <img src="https://img.shields.io/badge/3D%20Rendering-PyVista%20%2F%20VTK-orange" alt="PyVista 3D" />
  <img src="https://img.shields.io/badge/Status-Production%20Ready-brightgreen" alt="Status" />
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License" />
</p>

<p align="center">
  <strong>Desarrollado por:</strong> Félix Fernando Bautista Layme<br>
  <em>Universidad Nacional del Altiplano — Puno (UNA Puno)<br>
  Facultad de Ingeniería de Minas (FIM)</em>
</p>

---

## 📌 Descripción General

**X-BLAST Enterprise v2.0 (PERVOL)** es una suite computacional de alta ingeniería diseñada para el diseño tridimensional de mallas de perforación, modelado termodinámico de explosivos, análisis de secuencias de detonación y predicción geomecánica avanzada de fragmentación y daño por vibración.

Combina una interfaz gráfica moderna tipo CAD con renderizado 3D acelerado por hardware (PyVista/VTK), optimización estocástica de tiempos de retardo y generación automática de reportes corporativos en PDF.

<p align="center">
  <img src="assets/DIAGRAMA DE FLUJO PROGRAMA.png" alt="Diagrama de Flujo del Programa" width="750" />
</p>

---

## ✨ Características Principales

- **📐 Diseño Paramétrico de Mallas 3D**:
  - Cálculo trigonométrico de Burden (\(B\)), Espaciamiento (\(S\)), Taco (\(T\)), Subperforación (\(J\)) y sobreperforación.
  - Soporte para taladros verticales e inclinados con orientación azimutal y dip verdadero.
- **🗺️ Integración con Datos Topográficos y de Sondajes Reales**:
  - Carga nativa de archivos **TURPO** (`datos TURPO.csv`) con alineación espacial y corrección de longitudes.
  - Interpolación de superficie topográfica real mediante triangulación Delaunay 3D (`Topografia.csv`).
- **🧨 Modelado Físico y Termodinámico de Cargas**:
  - Banco de datos con explosivos industriales (ANFO, Emulsiones bombeables, Dinamitas, HA-46).
  - Configuración de cebos/boosters, tacos intermedios (air decks) y cargas desacopladas de contorno.
- **⏱️ Secuencia de Salida y Análisis de Solapamiento**:
  - Simulación dinámica de tiempos con detonadores electrónicos y no eléctricos (NONEL).
  - Cálculo estocástico de probabilidad de corte o detonación fuera de secuencia (\(P_{OSD}\)).
- **💥 Simulación Dinámica de Detonación y Escombrera (Heave)**:
  - Animación 3D en tiempo real del frente de disparo y expulsión de escombrera.
- **📊 Fragmentación y Vibraciones**:
  - Curva de distribución granulométrica mediante el modelo **Kuz-Ram** y algoritmos de Cunningham.
  - Control de daño sísmico y velocidad pico de partícula (**PPV**) mediante la formulación de **Holmberg-Persson** y regla de 8 ms.
- **📑 Reportabilidad Automatizada**:
  - Generación de reportes técnicos ejecutivos, operativos y de SSOMA en PDF y HTML.

---

## 📁 Estructura del Repositorio

```
PROYECTO PERVOL /
├── .github/
│   └── workflows/
│       └── ci.yml             # Integración continua con GitHub Actions
├── assets/                    # Recursos visuales, logotipos y diagramas
│   ├── X-BLAST.ico            # Ícono oficial de la aplicación
│   ├── X-BLAST.png            # Banner e identidad corporativa
│   ├── unap.png               # Escudo Universidad Nacional del Altiplano
│   └── fim.png                # Escudo Facultad de Ingeniería de Minas
├── data/                      # Datasets de ejemplo (Mina / Perforación)
│   ├── datos TURPO.csv        # Archivo de perforación de taladros con dip y azimut
│   ├── Topografia.csv         # Nube de puntos para relieve de terreno
│   └── Coordenadas.csv        # Coordenadas simples de collar
├── docs/                      # Documentación técnica completa
│   ├── GUIA_USUARIO.md        # Manual de usuario paso a paso
│   ├── FORMATO_DATOS.md       # Especificación de formatos CSV
│   ├── MODELOS_FISICOS.md     # Formulaciones matemáticas (Kuz-Ram, Holmberg-Persson)
│   └── archive_notes/         # Historial y bitácoras de desarrollo archivadas
├── VOLADURA_PRO_10X/          # Código fuente del sistema
│   ├── main.py                # Punto de entrada principal (GUI PySide6 + PyVista)
│   ├── config.py              # Parámetros y constantes globales
│   ├── physics_engine.py      # Motor de fragmentación y vibraciones
│   ├── core/                  # Núcleo: geometría, macizo rocoso, explosivos, timing
│   ├── gui/                   # Paneles por pestañas, visor 3D y barra CAD
│   ├── optimization/          # Motor de costos y simulación Monte Carlo
│   ├── reports/               # Orquestador de plantillas y generador PDF
│   └── test_*.py              # Suite de pruebas unitarias y de validación
├── archive/                   # Prototipos legacy archivados
├── .gitignore                 # Configuración de exclusión para Git
├── requirements.txt           # Dependencias del proyecto
├── run.bat                    # Lanzador para Windows (detecta entorno virtual o Python)
└── run.sh                     # Lanzador para Linux y macOS
```

---

## 🚀 Instalación y Puesta en Marcha

### Prerrequisitos
Tener instalado **Python 3.10 o superior**.

### 1. Clonar el Repositorio
```bash
git clone https://github.com/tu-usuario/pervol-xblast.git
cd pervol-xblast
```

### 2. Crear y Activar Entorno Virtual
```bash
# Crear entorno virtual
python -m venv venv

# En Windows:
venv\Scripts\activate

# En Linux / macOS:
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Ejecutar la Aplicación

- **Opción A (Windows - Recomendada)**:
  Doble clic en `run.bat` en la raíz del proyecto.
- **Opción B (Linux / macOS)**:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
- **Opción C (Terminal / Comando directo)**:
  ```bash
  cd VOLADURA_PRO_10X
  python main.py
  ```

---

## 🧪 Ejecución de Pruebas Automatizadas

El proyecto incluye tests matemáticos y unitarios que validan la trigonometría, termodinámica y geomecánica:

```bash
cd VOLADURA_PRO_10X

# Validar geometría 3D, masa de carga y geomecánica
python -X utf8 test_phase1.py

# Validar termodinámica de explosivos y solapamiento estocástico
python -X utf8 test_advanced_physics.py

# Validar carga de taladros TURPO y alineación topográfica
python -X utf8 test_turpo_solution.py
```

---

## 📚 Documentación Adicional

Para más detalles, consulta los manuales en la carpeta [`docs/`](docs/):
- [📘 Guía Completa de Usuario](docs/GUIA_USUARIO.md)
- [📋 Especificación de Formatos de Datos](docs/FORMATO_DATOS.md)
- [🔬 Modelos Físicos y Matemáticos](docs/MODELOS_FISICOS.md)

---

## 👨‍💻 Autor

**Félix Fernando Bautista Layme**  
Ingeniería de Minas — Universidad Nacional del Altiplano (UNA Puno)  
Puno, Perú 🇵🇪
