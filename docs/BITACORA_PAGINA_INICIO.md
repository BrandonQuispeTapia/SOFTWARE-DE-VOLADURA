# BITÁCORA DE CAMBIOS: IMPLEMENTACIÓN DE LA PÁGINA DE INICIO (START PAGE)
**X-BLAST Enterprise v3.0 — Suite de Diseño y Optimización de Voladura**  
*Universidad Nacional del Altiplano - Puno | Facultad de Ingeniería de Minas*  
*Fecha:* 01 de Septiembre de 2026  

---

## 1. Contexto y Requerimiento
El usuario solicitó incorporar una **Página de Inicio / Pantalla de Bienvenida** (Start Page) para X-BLAST, análoga a las pantallas de inicio de aplicaciones profesionales de ingeniería y productividad como **ArcGIS Pro, Datamine Studio y Microsoft Word**.

### Criterios Clave de Diseño:
- **Flujo de Usuario:** No ingresar directamente a la interfaz de trabajo 3D sobrecargada de controles, sino presentar primero una página de bienvenida para elegir qué hacer.
- **Estética Minimalista en Tono Blanco:** Superficies limpias en blanco (`#FFFFFF`), fondos suaves (`#F8FAFC`), bordes sutiles (`#E2E8F0`), acentos en azul minero (`#0284C7`), y tipografía clara y jerarquizada.
- **Funcionalidad Completa:** Selección de plantillas, carga rápida de datos de mina (TURPO, Topografía), historial de proyectos recientes con persistencia, buscador, visor de documentación y créditos institucionales.
- **Navegación Bidireccional:** Posibilidad de volver a la página de inicio desde la interfaz principal de trabajo en cualquier momento mediante el menú o la barra de herramientas.

---

## 2. Archivos Creados y Modificados

### A. Nuevos Componentes
1. **`xblast/ui/start_page.py`** (Nuevo módulo):
   - **`StartWindow`:** Ventana principal de bienvenida (1180x750 px) con arquitectura modular.
   - **Barra Lateral Izquierda (Navigation Rail):**
     - Identidad de marca (Logo vectorial, nombre X-BLAST, versión 3.0 Enterprise).
     - Botones de navegación con estados activos: *Inicio*, *Nuevo Proyecto*, *Abrir Archivo...*, *Guía de Usuario*, *Acerca de*.
     - Tarjeta institucional inferior con los créditos de la Universidad Nacional del Altiplano - Puno (UNA Puno), Facultad de Ingeniería de Minas (FIM) y Félix Fernando Bautista Layme.
   - **Área Central (Dashboard):**
     - **Cabecera de bienvenida:** Saludo y subtítulo de la suite.
     - **Plantillas de Voladura (Cards interactivas con hover y pastillas de color):**
       1. *Malla Paramétrica (Banco Estándar):* Diseño geométrico regular con Konya.
       2. *Malla Real TURPO (228 taladros):* Carga directa del dataset de perforación real con orientación espacial (Azimuth y Dip).
       3. *Topografía y Mina Modelo:* Nube topográfica 3D (triangulación Delaunay) y collares de taladro.
       4. *Importar Archivo Externo:* Explorador de archivos para formatos `.xbp`, `.csv` y `.txt`.
     - **Lista de Proyectos y Archivos Recientes:**
       - Tabla interactiva con icono de tipo, nombre, directorio y última fecha de modificación.
       - Doble clic o selección para abrir inmediatamente.
       - Filtro/buscador en tiempo real de archivos recientes.
     - **Novedades y Asistencia Técnica:** Consejos rápidos sobre la navegación orbital 3D, edición por plataformas (decks) y modelos físicos Kuz-Ram.
   - **Página de Documentación Técnica:** Visor embebido con formato Markdown para leer la guía de usuario sin salir del programa.
   - **Página Acerca de:** Información institucional, tecnologías empleadas y atribuciones académicas.
   - **`RecentProjectsManager`:** Administrador de archivos recientes persistente mediante `QSettings` (`UNA_Puno_FIM/X-BLAST`). Si la lista está vacía, descubre y sugiere automáticamente los datos de ejemplo del repositorio.
   - **`find_data_file`:** Localizador automático y tolerante a rutas para datasets locales y de carpetas superiores.

2. **`tests/test_start_page.py`** (Nuevas pruebas unitarias):
   - Cobertura de inicialización de `StartWindow`, administrador de proyectos recientes, búsqueda de archivos y despacho de señales.

### B. Modificaciones en el Núcleo
1. **`xblast/app.py`:**
   - Redirigido el punto de entrada para iniciar con `StartWindow` en lugar de abrir directamente el lienzo 3D.
   - Soporte para argumentos de línea de comandos: si el usuario pasa un archivo por parámetro (ej. asociar `.xbp`), se abre directamente el espacio de trabajo; si no, abre la página de inicio.
   - Manejador de transición suave que destruye la página de inicio y despliega la ventana principal con el proyecto seleccionado.

2. **`xblast/ui/main_window.py`:**
   - Añadido soporte para `initial_mode` y `initial_path` en `__init__` y `_bootstrap`.
   - Incorporada la acción **`act_home`** (*Página de inicio...*, atajo `Ctrl+H`) en la barra de herramientas principal y como primera opción del menú **Archivo**.
   - Implementado el método `open_start_page()`, que valida cambios sin guardar antes de retornar limpiamente a la pantalla de bienvenida.
   - Integrado `RecentProjectsManager.add_recent()` en la apertura, importación y guardado de proyectos y coordenadas.

3. **`xblast/ui/icons.py`:**
   - Agregados nuevos iconos vectoriales generados dinámicamente con `QPainter`:
     - `"home"` (Casita para inicio)
     - `"doc"` (Documento / manual)
     - `"cube"` (Cubo isométrico 3D)
     - `"arrow_right"` (Flecha indicadora)
     - `"star"` (Estrella de favoritos / plantillas)
     - `"search"` (Lupa de búsqueda)

---

## 3. Pruebas y Verificación
- **Pruebas Automatizadas:** 51 de 51 pruebas aprobadas con éxito (`pytest`, tiempo: ~3.2 segundos).
- **Ejecución en Vivo en Entorno Windows:**
  - Lanzamiento verificado con `run.bat` y `python -m xblast`.
  - La ventana de inicio abre en blanco minimalista en el centro de la pantalla.
  - Al seleccionar "Malla Paramétrica", "Malla Real TURPO" o "Topografía y Mina", transiciona instantáneamente al espacio de trabajo cargando los taladros correspondientes.
  - Desde el menú `Archivo -> Página de inicio...` (o pulsando `Ctrl+H`), se puede volver a la página de bienvenida en cualquier momento.

---
*Fin de la bitácora.*
