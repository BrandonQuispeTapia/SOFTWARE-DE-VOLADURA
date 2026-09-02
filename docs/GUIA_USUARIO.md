# Guía de usuario

Cómo llevar un disparo desde los parámetros iniciales hasta el reporte firmado.

---

## 1. Arranque

Ejecute `run.bat` (Windows), `./run.sh` (Linux/macOS) o `python -m xblast`.

La aplicación abre con una malla de ejemplo ya generada y analizada: 60
taladros de 152 mm, banco de 10 m, ANFO en columna y emulsión de fondo. Sirve
para reconocer la interfaz antes de cargar datos propios.

### El área de trabajo

| Zona | Contenido |
| --- | --- |
| **Izquierda, arriba** | Explorador de capas: enciende y apaga taladros, cargas, etiquetas, topografía, cara libre, piso de banco y campo de energía. Debajo, el listado de taladros por tipo. |
| **Izquierda, abajo** | Pestañas **Diseño** (geometría, macizo, entorno), **Carga** y **Secuencia**. |
| **Centro** | Visor 3D. Rueda para acercar, arrastre para rotar, clic derecho arrastrando para desplazar. |
| **Derecha** | Pestañas **Resultados**, **Propiedades** del taladro seleccionado y **Optimización**. |
| **Abajo** | **Bitácora** de la sesión y **Tabla** completa de taladros. |

Todos los paneles se pueden mover, apilar, sacar como ventana flotante o
cerrar. `Ver ▸ Restablecer paneles` vuelve a la disposición original.

---

## 2. Definir el macizo rocoso

**Diseño ▸ Macizo.** Es el primer paso: el factor de roca condiciona todo lo
demás.

1. Elija la litología o escriba la suya.
2. Ajuste densidad, resistencia a compresión, módulo de Young y velocidad de
   onda P con datos de laboratorio o de la base geotécnica de la mina.
3. Describa la estructura tal como se ve en la cara: tipo de macizo,
   espaciamiento de juntas y orientación respecto a la cara libre.

Al pie del panel aparecen el índice de volabilidad, el factor de roca `A` y la
clasificación. Un `A` entre 4 y 6 corresponde a roca media; sobre 10, a roca
muy dura.

---

## 3. Geometría de la malla

**Diseño ▸ Geometría.**

1. Fije el diámetro de perforación y la altura de banco.
2. Pulse **Calcular B, S, taco y subperforación**: el programa promedia cuatro
   métodos clásicos, descarta los valores atípicos y corrige por relación de
   rigidez. El texto bajo el botón muestra qué dio cada método.
3. Ajuste filas, columnas y disposición (tresbolillo mejora la uniformidad).
4. **Azimut de salida** es la dirección hacia la cara libre. Ordena la
   secuencia y determina el burden real de cada taladro: verifíquelo contra el
   plano de la mina.

El bloque **Verificación** tiñe en verde, ámbar o rojo las cuatro relaciones de
control. Corrija cualquier valor en rojo antes de continuar.

Pulse **Generar malla** (o `F5`).

---

## 4. Diseño de carga

**Carga.** Los cambios se reflejan de inmediato en el esquema de la columna y
en el resumen del taladro tipo.

- **Columna**: explosivo principal y acoplamiento. Deje 1.00 para producción;
  baje a 0.5 o menos para precorte y recorte.
- **Carga de fondo**: producto de mayor densidad y energía para romper el pie.
  Dos a tres metros suele bastar.
- **Plataformas**: dividir la carga baja la carga operante —y con ella la
  vibración— y mejora la distribución de energía en bancos altos.
- **Cámara de aire**: ahorra explosivo manteniendo la fragmentación en la
  parte alta del banco.
- **Taco de collar**: no baje de 22 diámetros. El panel de revisión avisa si el
  taco es insuficiente, que es la causa más común de proyección.

---

## 5. Secuencia de salida

**Secuencia.**

1. Elija el sistema de iniciación. El electrónico tiene una dispersión de
   0.02 % frente al 3 % del pirotécnico: la diferencia se nota en la
   probabilidad de solape.
2. Seleccione el patrón de amarre y los retardos.
3. El bloque **Verificación temporal** muestra el alivio en ms por metro. Los
   valores deben quedar en verde: 3–6 ms/m entre taladros y 10–30 ms/m entre
   filas.
4. El gráfico muestra la carga detonada por ventana de cooperación con la
   línea de la carga máxima admisible para el límite de PPV declarado. Ninguna
   barra debería superarla.

**Animar secuencia** (`F8`) reproduce el disparo sobre el visor 3D.

---

## 6. Entorno y límites

**Diseño ▸ Entorno.**

1. Ubique el receptor sensible —vivienda, estructura, instrumento— con sus
   coordenadas reales.
2. Declare el PPV admisible (12.7 mm/s es el criterio USBM para vivienda con
   acabado de yeso), el límite de onda aérea y el radio de exclusión.
3. Ajuste las constantes de sitio `K` y `β`. **Los valores por defecto son
   genéricos**: sustitúyalos por la regresión de su propio monitoreo
   sismográfico en cuanto tenga registros.

---

## 7. Analizar

Pulse **Analizar** (`F6`). El cálculo corre en segundo plano.

### Resumen
Tablero con producción, carga, fragmentación, control ambiental y economía. La
etiqueta de calidad resume el diseño de 0 a 100.

### Revisión
La lista de hallazgos ordenada por severidad. Cada uno dice qué está mal, por
qué importa y qué corregir. **Los críticos deben resolverse antes de
disparar.**

### Fragmentación
Curva granulométrica de Swebrec con X50, P80 y el umbral de sobretamaño, más
el histograma de dispersión del burden en la malla.

### Ambiental
Sismograma previsto en el receptor con las líneas de límite, cumplimiento
contra USBM y DIN, radio de daño al talud remanente, onda aérea y alcance de
proyección.

### Costos
Desglose por concepto y reparto entre perforación-voladura y aguas abajo.

---

## 8. Tematizar el visor

El desplegable **Tematizar por** de la barra de herramientas colorea la malla
según la variable elegida:

| Tema | Para qué sirve |
| --- | --- |
| Tipo de taladro | Distinguir producción, precorte, recorte y alivio |
| Retardo | Verificar visualmente el amarre |
| Factor de potencia | Detectar zonas con exceso o falta de explosivo |
| Burden real / de alivio | Localizar taladros con burden corto — riesgo de proyección |
| X50 previsto | Anticipar dónde saldrán los bolones |
| Confinamiento | Ver qué taladros disparan contra roca cerrada |

**Campo de energía** superpone las isosuperficies de energía explosiva: las
zonas frías son las que dejarán bolones y lomos.

---

## 9. Optimizar

**Optimización** (`F7`) explora variaciones de burden y relación S/B alrededor
del diseño actual, manteniendo constante el área volada para que la
comparación sea válida.

Cada escenario se evalúa con el motor completo. Los que incumplen PPV, onda
aérea, distancia de proyección, P80 objetivo o relación de rigidez se marcan
como no viables. El recuadro superior recomienda el de menor costo total por
tonelada y cuánto ahorra frente al diseño actual.

**Aplicar mejor escenario** lleva esos parámetros al panel de diseño y
regenera la malla.

> El mínimo del costo total rara vez coincide con el mínimo de perforación y
> voladura: cerrar la malla encarece el disparo pero abarata carguío, acarreo
> y chancado. Ese es el punto que busca la optimización.

---

## 10. Importar datos reales

### Taladros
**Importar taladros** (`Ctrl+I`) acepta tanto un CSV de collares
(`ID;X;Y;Z`) como un archivo de perforación completo con `ELEV TOE`,
`LENGTH`, `AZ` y `DIP`. El delimitador, la codificación y los nombres de
columna se detectan solos. Si `LENGTH` viene en cero, la longitud se deduce de
la diferencia de cotas.

### Topografía
**Importar topografía** carga la nube de puntos, la tría por Delaunay y apoya
los collares sobre la superficie manteniendo la cota de piso, que es la
práctica real en banco.

El formato completo está en [FORMATO_DATOS.md](FORMATO_DATOS.md).

---

## 11. Entregables

| Acción | Resultado |
| --- | --- |
| **Reporte técnico** (`Ctrl+R`) | Documento HTML autocontenido con la memoria de cálculo completa, gráficos incrustados y el detalle de todos los taladros. Ábralo en el navegador e imprima a PDF. |
| **Exportar taladros** | CSV con coordenadas, carga, retardo, burden y factor de potencia por taladro, listo para el área de operaciones. |
| **Captura del visor** | PNG de la vista 3D actual. |
| **Guardar proyecto** (`Ctrl+S`) | Archivo `.xbp` con todo el diseño, incluida la topografía. |

---

## 12. Antes de usarlo en producción

Los modelos son predictivos y traen constantes genéricas. Calíbrelos con datos
de su yacimiento:

1. **Constantes de sitio `K` y `β`**: regresión sobre registros del
   sismógrafo. Es lo que más cambia entre operaciones.
2. **Factor de roca `A`**: contraste el X50 predicho con análisis
   granulométrico de imágenes de la escombrera y ajuste los componentes del
   índice de Lilly.
3. **Costos unitarios**: reemplace los valores por defecto por los reales de
   perforación, explosivos, carguío, acarreo y chancado.
4. **Desviación de perforación**: mídala con sonda de desviación; entra
   directamente en el índice de uniformidad.

---

## Atajos

| Tecla | Acción |
| --- | --- |
| `F5` | Generar malla |
| `F6` | Analizar |
| `F7` | Optimizar |
| `F8` | Animar secuencia |
| `Ctrl+1` … `Ctrl+4` | Vista isométrica, planta, perfil frontal, perfil lateral |
| `Ctrl+0` | Encuadrar |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` | Nuevo, abrir, guardar proyecto |
| `Ctrl+I` | Importar taladros |
| `Ctrl+R` | Reporte técnico |
| `Ctrl+Alt+1` … `Ctrl+Alt+9` | Mostrar u ocultar cada panel |
