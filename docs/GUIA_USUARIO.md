# Guía de Usuario: X-BLAST Enterprise v2.0 (PERVOL)

**Sistema Integral de Simulación, Diseño y Optimización de Perforación y Voladura de Rocas**  
*Autor: Félix Fernando Bautista Layme — Universidad Nacional del Altiplano, Puno (Facultad de Ingeniería de Minas)*

---

## 1. Introducción

**X-BLAST Enterprise v2.0** es una plataforma de ingeniería minera diseñada para modelar, simular y optimizar mallas de perforación y voladura en minería a cielo abierto y subterránea. Integra motores de física avanzada, visualización 3D interactiva en tiempo real y generación automatizada de reportes técnicos ejecutivos.

---

## 2. Requisitos y Puesta en Marcha

### Requisitos del Sistema
- **Sistema Operativo**: Windows 10/11, Linux, macOS.
- **Python**: 3.10, 3.11, 3.12 o 3.13 (64-bit).
- **Librerías principales**: `PySide6`, `pyvista`, `pyvistaqt`, `numpy`, `scipy`, `matplotlib`, `jinja2`, `weasyprint` o `fpdf2`.

### Instalación Rápida
1. Clona el repositorio o sitúate en la carpeta raíz del proyecto.
2. Crea y activa un entorno virtual (recomendado):
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux / macOS:
   source venv/bin/activate
   ```
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Inicia el programa:
   - **En Windows**: Haz doble clic en `run.bat` o ejecuta `X-BLAST.bat`.
   - **En Linux / macOS**: Ejecuta `./run.sh`.
   - **Por comando directo**:
     ```bash
     cd VOLADURA_PRO_10X
     python main.py
     ```

---

## 3. Flujo de Trabajo en la Interfaz Gráfica

La interfaz principal cuenta con un sistema de 4 pestañas de ingeniería organizadas secuencialmente:

### 📐 Pestaña 1: Parámetros de Malla (Grid Design)
- **Burden (\(B\))**: Distancia perpendicular a la cara libre (ej. 4.5 m).
- **Espaciamiento (\(S\))**: Distancia entre taladros de una misma fila (ej. 5.0 m).
- **Diámetro (\(\phi_b\))**: Diámetro de perforación en milímetros (ej. 102 mm o 165 mm).
- **Altura de Banco (\(H\))**: Altura del banco en metros (ej. 12.0 m).
- **Subperforación (\(J\))**: Longitud perforada bajo la cota de rasante (ej. 1.0 m).
- **Inclinación y Azimut**: Configuración de dip e inclinación para tiros inclinados.
- **Botón "Calcular Malla"**: Genera la matriz de taladros y los renderiza automáticamente en el visor 3D interactivo.

### 🧨 Pestaña 2: Cebado y Carga de Explosivos
- **Carga de Columna**: Selección del agente de voladura principal (ANFO estándar, HA 46, Emulsión bombeable, dinamita).
- **Sistema de Iniciación**: Booster / primer (Pentolita 150g, 450g, etc.).
- **Longitud de Taco (Stemming)**: Longitud del material inerte de confinamiento.
- **Carga en Fondos**: Permite configurar cargas de fondo diferenciadas.

### ⏱️ Pestaña 3: Secuencia de Salida y Tiempos
- **Líneas de Superficie y Fondo**: Retardos electrónicos o no eléctricos (NONEL) de 9ms, 17ms, 25ms, 42ms o programables al milisegundo.
- **Análisis de Tiros Cortados y Solapamiento**: Motor estocástico que calcula la probabilidad de detonación fuera de orden (\(P_{OSD}\)) y alerta sobre riesgos (Bajo, Medio, Alto).
- **Simulación 3D de Disparo**: Animación en tiempo real de la detonación taladro por taladro con desplazamiento de escombrera (heave).

### 📊 Pestaña 4: Resultados y Reportes
- **Predicción de Fragmentación (Kuz-Ram)**: Curva granulométrica con cálculo de \(X_{50}\) y \(P_{80}\).
- **Control de Vibraciones (Holmberg-Persson)**: Estimación de velocidad pico de partícula (PPV) y radio de daño.
- **Costos y KPI**: Costo total de perforación, accesorios y explosivo por tonelada y metro cúbico.
- **Exportación PDF**: Generación de reportes corporativos (Ejecutivo, Operativo, Carga, SSOMA).

---

## 4. Carga de Datos Reales de Mina

El sistema permite importar archivos CSV directamente desde la pestaña de diseño o desde scripts:

1. **Taladros TURPO (`data/datos TURPO.csv`)**:
   - Carga coordenadas reales con elevaciones de collar y fondo, azimut e inclinación.
   - En el panel lateral, haz clic en **"TALADROS (TURPO)"** y selecciona el archivo.
2. **Topografía de Terreno (`data/Topografia.csv`)**:
   - Genera una malla de superficie triangulada (Delaunay 3D) que representa el relieve real.
   - Haz clic en **"TOPOGRAFIA"** y selecciona el archivo de nube de puntos.

---

## 5. Pruebas Automatizadas

El proyecto incluye una suite completa de pruebas unitarias para validar las matemáticas y la física:

```bash
cd VOLADURA_PRO_10X
python -X utf8 test_phase1.py           # Valida geometría 3D, masa de carga y geomecánica
python -X utf8 test_advanced_physics.py # Valida termodinámica y solapamiento estocástico
python -X utf8 test_turpo_solution.py   # Valida parsing TURPO y cilindros 3D
```
