<p align="center">
  <img src="assets/X-BLAST.png" alt="X-BLAST" width="200" />
</p>

<h1 align="center">X-BLAST</h1>

<p align="center"><strong>Plataforma de diseño, simulación y optimización de voladura de rocas</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%20–%203.13-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt&logoColor=white" alt="PySide6" />
  <img src="https://img.shields.io/badge/3D-PyVista%20%2F%20VTK-E85D2B" alt="PyVista" />
  <img src="https://img.shields.io/badge/Licencia-MIT-1a7f4b" alt="MIT" />
</p>

<p align="center">
  Facultad de Ingeniería de Minas · Universidad Nacional del Altiplano — Puno
</p>

---

## Qué hace

X-BLAST no se limita a dibujar una malla: **evalúa el disparo completo** y dice
si va a funcionar. El flujo de trabajo es el de una oficina de perforación y
voladura real.

```
Geometría ─▶ Carga ─▶ Secuencia ─▶ Análisis ─▶ Optimización ─▶ Reporte
```

| Módulo | Qué resuelve |
| --- | --- |
| **Geometría** | Mallas cuadradas, rectangulares y al tresbolillo con taladros inclinados, orientadas al azimut de la cara libre y apoyadas sobre topografía real. Dimensionamiento automático que promedia Konya-Walter, Langefors-Kihlström, Ash y Pearse. |
| **Burden real** | Cada taladro recibe su burden geométrico y su **burden de alivio** —la cara efectiva en el instante en que dispara— y un volumen de responsabilidad por teselación de Voronoi, en lugar del clásico B×S×H uniforme. |
| **Carga** | Columna por plataformas: carga de fondo, columnas múltiples, tacos intermedios, cámara de aire y taco de collar, con acoplamiento variable para voladura controlada. Catálogo de once agentes de voladura comerciales. |
| **Secuencia** | Tres métodos intercambiables: patrón de amarre, **vector de dirección** —se dibuja la flecha y los tiempos salen de BRB y BRS, en ms por metro— y salida radial desde un punto. Cinco patrones de amarre, carga operante por ventana de cooperación (regla de 8 ms) y probabilidad de solape por Monte Carlo. |
| **Detonadores electrónicos** | Catálogo de once modelos con su rango programable, incremento mínimo y precisión real, que alimenta la dispersión simulada. Los tiempos se ajustan al incremento del modelo y se validan contra sus límites antes de exportarlos. |
| **Plataformas retardadas** | Retardo entre cargas independientes del mismo taladro y entre cebos de una misma carga. La carga operante se cuenta por carga real, no por taladro: seccionar la columna solo baja la vibración si el cálculo lo reconoce. |
| **Isócronas y recorrido** | Curvas de igual tiempo de detonación sobre la malla y trazado del orden de salida, para leer de un vistazo por dónde corre y dónde se atasca el disparo. |
| **Fragmentación** | Kuznetsov-Cunningham para el X50, índice de uniformidad de Cunningham corregido por tiempo de alivio, y curva completa de **Swebrec (KCO)**, que no sobreestima los finos como Rosin-Rammler. |
| **Vibraciones** | Distancia escalada USBM en campo lejano, Holmberg-Persson en campo cercano para el daño al talud remanente, y **superposición de onda semilla** para predecir el sismograma completo del disparo. Cumplimiento contra USBM RI8507 y DIN 4150-3. |
| **Onda aérea y proyección** | Sobrepresión con corrección por confinamiento del taco e inversión térmica; alcance de flyrock por Richards & Moore y Lundborg, con distancia segura recomendada. |
| **Campo de energía** | Malla 3D de energía explosiva en MJ/m³ que muestra dónde queda roca sub-energizada (bolones, lomos) y dónde sobra energía (finos, proyección). |
| **Economía** | Modelo mina-planta: el costo de carguío, acarreo y chancado escala con el tamaño medio de fragmento, así que la malla más barata en voladura casi nunca es la más barata por tonelada. |
| **Optimización** | Barrido de burden y relación S/B evaluando cada escenario con el motor completo, descartando los que incumplen los límites ambientales y proponiendo el de menor costo total por tonelada. |
| **Visor 3D** | Navegación completa —órbita, terreno, joystick y planta 2D—, giro alrededor del taladro seleccionado, vistas normalizadas, proyección ortográfica y exageración vertical. Selección por clic, por ventana, por tipo o desde la tabla. |
| **Personalización** | 229 opciones en 17 categorías: paleta y tipografía, aspecto del visor, colores por tipo de taladro, interacción, capas, animación, gráficos, unidades, valores por defecto del diseño, parámetros de análisis, límites normativos y costos. Se aplican en caliente y viajan en un archivo exportable. |
| **Edición por taladro** | Cada taladro se abre y se interviene: tipo, geometría, retardo y columna de carga plataforma por plataforma. Los cambios manuales quedan protegidos de la regla global y se replican sobre la selección. |
| **Revisión** | Más de veinte reglas de buena práctica (H/B, S/B, T/B, B/D, tiempos de alivio, taco mínimo, diámetro crítico del explosivo…) que califican el diseño de 0 a 100 y explican cada hallazgo. |

Todo se consolida en un **reporte técnico HTML autocontenido**, listo para
imprimir o exportar a PDF desde el navegador.

---

## Instalación

Requiere **Python 3.10 o superior**.

```bash
git clone https://github.com/BrandonQuispeTapia/SOFTWARE-DE-VOLADURA.git
cd SOFTWARE-DE-VOLADURA

python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate        # Linux / macOS

pip install --upgrade pip
pip install -r requirements.txt
```

## Ejecución

| Sistema | Comando |
| --- | --- |
| Windows | doble clic en `run.bat` |
| Linux / macOS | `./run.sh` |
| Cualquiera | `python -m xblast` |

La aplicación arranca con una malla de ejemplo ya analizada, de modo que el
visor nunca aparece vacío.

---

## La interfaz

Interfaz de escritorio clara, en la línea de las suites técnicas tipo SIG:
visor 3D al centro, paneles acoplables y reordenables alrededor.

```
┌──────────────────────────────────────────────────────────────────────┐
│  Barra de herramientas: proyecto · importar · generar · analizar     │
├────────────────┬──────────────────────────────┬──────────────────────┤
│  Explorador    │                              │  Resultados          │
│  de capas      │                              │  Propiedades         │
├────────────────┤        Visor 3D              │  Optimización        │
│  Diseño        │                              │                      │
│  Carga         │                              │                      │
│  Secuencia     │                              │                      │
├────────────────┴──────────────────────────────┴──────────────────────┤
│  Bitácora · Tabla de taladros                                        │
└──────────────────────────────────────────────────────────────────────┘
```

La malla 3D se puede tematizar por tipo de taladro, retardo, factor de
potencia, carga, burden real, burden de alivio, X50 previsto o confinamiento;
la secuencia de salida se reproduce como animación sobre el visor.

**Ratón en el visor**

| Acción | Resultado |
| --- | --- |
| Arrastrar con el izquierdo | Girar |
| Rueda | Acercar y alejar |
| Botón central, o Shift + izquierdo | Desplazar |
| Doble clic | Seleccionar el taladro |
| Dos clics en modo vector | Colocar el vector de dirección |
| Ctrl + clic · Shift + clic | Agregar a la selección · alternar |

Girar y seleccionar comparten el botón izquierdo: se distingue el clic del
arrastre por el desplazamiento del puntero, así que ninguna de las dos cosas le
quita el botón a la otra. Si prefiere seleccionar con una sola pulsación,
cámbielo en **Preferencias > Interacción**.

La cámara trabaja en modo **tornamesa**: gira alrededor del eje vertical con la
elevación acotada, de modo que el modelo nunca queda de cabeza por seguir
arrastrando. Quien prefiera el giro esférico clásico lo tiene en el mismo
desplegable.

**Atajos**: `F5` generar malla · `F6` analizar · `F7` optimizar · `F8` animar ·
`Ctrl+1..4` vistas · `Ctrl+0` encuadrar · `Ctrl+R` reporte ·
`Ctrl+A` seleccionar todo · `Ctrl+D` quitar selección · `B` selección por
ventana. Sobre el visor: flechas para girar, `F` centrar en la selección,
`R` encuadrar, `P` proyección, `Esc` deseleccionar. `Ctrl+,` abre las
preferencias.

---

## Datos de entrada

Los importadores detectan solos el delimitador, la codificación y los nombres
de columna, así que los archivos de campo se cargan sin editarlos.

| Archivo | Columnas reconocidas |
| --- | --- |
| Collares | `ID` / `BHID`, `X` / `ESTE` / `EASTING`, `Y` / `NORTE`, `Z` / `COTA` |
| Perforación completa (TURPO) | además `ELEV TOE`, `LENGTH`, `AZ`, `DIP`, `MATERIAL` |
| Topografía | `XP` / `YP` / `ZP` o `X` / `Y` / `Z` |

Cuando `LENGTH` viene en cero —lo habitual en las exportaciones de campo— la
longitud se deduce de la diferencia de cotas y del buzamiento.

En [`data/`](data/) hay tres conjuntos de ejemplo reales. El formato está
detallado en [`docs/FORMATO_DATOS.md`](docs/FORMATO_DATOS.md).

---

## Estructura

```
xblast/
├── core/              Motor de ingeniería (sin dependencias de interfaz)
│   ├── models.py          Taladro, macizo, explosivo, diseño
│   ├── explosives.py      Catálogo de agentes, cebos y tacos
│   ├── pattern.py         Generación de mallas y fórmulas de dimensionamiento
│   ├── charging.py        Columna de carga por plataformas
│   ├── burden.py          Burden real, alivio y volúmenes de responsabilidad
│   ├── timing.py          Secuencia, cooperación y dispersión
│   ├── fragmentation.py   Kuz-Ram, Cunningham y Swebrec
│   ├── vibration.py       PPV lejano y cercano, superposición y normativa
│   ├── airblast.py        Onda aérea y proyección de rocas
│   ├── energy.py          Campo 3D de energía
│   ├── costs.py           Modelo de costos mina-planta
│   ├── optimizer.py       Barrido de escenarios
│   └── analysis.py        Orquestador del análisis completo
├── dataio/            Importadores de campo y persistencia de proyectos
├── ui/                Interfaz: tema, widgets, visor 3D, gráficos y paneles
└── reports/           Reporte técnico HTML

data/                  Conjuntos de ejemplo
docs/                  Guía de usuario, formatos y modelos físicos
tests/                 Suite de pruebas del motor
```

El motor es independiente de la interfaz: `xblast.core` y `xblast.reports` se
pueden usar desde un script sin instalar PySide6.

```python
from xblast.core import pattern, charging
from xblast.core.analysis import analyze
from xblast.core.charging import ChargeRule
from xblast.core.models import BlastDesign

d = BlastDesign(name="Banco 3420")
d.holes = pattern.generate_pattern(d.pattern)
charging.apply_charge(d.holes, ChargeRule(stemming_m=d.pattern.stemming_m))

a = analyze(d)
print(f"X50 {a.kpis['x50_cm']:.1f} cm · PPV {a.kpis['ppv_mm_s']:.1f} mm/s")
```

---

## Pruebas

```bash
pytest tests -q
```

La suite cubre geometría, carga, burden, secuencia, fragmentación, vibración,
proyección, costos, importadores y persistencia, y corre sin interfaz gráfica.

---

## Modelos empleados

Las formulaciones y sus referencias están en
[`docs/MODELOS_FISICOS.md`](docs/MODELOS_FISICOS.md): Lilly (1986),
Kuznetsov-Cunningham (1987), Ouchterlony (2005), Konya-Walter (1972),
Langefors-Kihlström (1963), Holmberg-Persson (1979), Siskind (1980),
Richards & Moore (2004) y la norma DIN 4150-3.

> Los modelos son predictivos. Antes de usarlos como base de decisión
> operativa hay que calibrarlos con mediciones del propio yacimiento:
> constantes de sitio `K` y `β` del monitoreo sismográfico, factor de roca `A`
> con análisis granulométrico de imágenes, y costos unitarios con datos de la
> operación.

---

## Documentación

- [Guía de usuario](docs/GUIA_USUARIO.md) — flujo de trabajo paso a paso
- [Formato de datos](docs/FORMATO_DATOS.md) — especificación de los CSV
- [Modelos físicos](docs/MODELOS_FISICOS.md) — formulaciones y referencias

---

## Autor

**Félix Fernando Bautista Layme**
Ingeniería de Minas — Universidad Nacional del Altiplano, Puno, Perú
