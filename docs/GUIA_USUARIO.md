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
| **Centro** | Visor 3D con su barra de cámara y selección. |
| **Derecha** | Pestañas **Resultados**, **Propiedades** del taladro seleccionado y **Optimización**. |
| **Abajo** | **Bitácora** de la sesión y **Tabla** completa de taladros. |

Todos los paneles se pueden mover, apilar, sacar como ventana flotante o
cerrar. `Ver ▸ Restablecer paneles` vuelve a la disposición original.

---

## 2. Moverse por el visor

### Ratón

| Acción | Resultado |
| --- | --- |
| Arrastrar con el izquierdo | Girar alrededor del punto focal |
| Rueda | Acercar y alejar |
| Botón central, o Shift + izquierdo | Desplazar |
| Botón derecho arrastrando | Zoom continuo |
| Doble clic | Seleccionar el taladro bajo el cursor |
| Ctrl + clic | Agregar a la selección |
| Shift + clic | Alternar ese taladro en la selección |

Girar y seleccionar comparten el botón izquierdo. El programa distingue el clic
del arrastre por lo que se desplaza el puntero, así que no hay que cambiar de
herramienta para pasar de una cosa a la otra. La selección va por defecto con
**doble clic**, que deja la pulsación simple entera para girar; en
**Preferencias > Interacción** se puede pasar a un solo clic y ajustar el radio
de captura y la tolerancia de arrastre.

No hace falta apuntar con precisión al eje del taladro: si la pulsación cae
dentro del radio de captura —16 píxeles por defecto—, el taladro más próximo se
selecciona igual.

### Barra del visor

| Control | Para qué sirve |
| --- | --- |
| **Navegación** | *Tornamesa* es el modo por defecto: gira alrededor del eje vertical con la elevación acotada, de manera que el modelo nunca se voltea por seguir arrastrando. *Órbita libre* es el giro esférico clásico, sin restricción y con posibilidad de rotar el encuadre. *Terreno* es el estilo de VTK para relieve. *Joystick* sigue moviendo mientras el botón siga pulsado. *Planta 2D* deja solo desplazamiento y zoom, con proyección ortográfica. |
| **Vista** | Isométrica, planta y las cuatro ortogonales por punto cardinal. |
| **Proyección** | Alterna entre perspectiva y ortográfica; la ortográfica es la que sirve para medir sobre el plano. |
| **Girar** | Las flechas orbitan alrededor del punto focal —el modelo no se mueve, la cámara sí—, y las dos curvas rotan el encuadre. Mantener pulsado repite el giro. |
| **Rotación automática** | Giro continuo, útil para revisar la malla sin manos o para grabar. |
| **Encuadrar todo / Encuadrar la selección** | Ajusta la cámara a todo el disparo o solo a lo seleccionado. |
| **Centrar el giro en la selección** | Mueve el punto focal al taladro elegido. A partir de ahí el visor gira **alrededor de ese taladro**, que es la forma de inspeccionarlo por todos lados sin perderlo de vista. |
| **Selección por ventana** | Encierra varios taladros con un rectángulo. Ctrl agrega, Shift quita, Esc cancela. |
| **Escala Z** | Exagera la vertical hasta 5x, para leer bancos bajos o taludes tendidos. |

### Teclado sobre el visor

| Tecla | Acción |
| --- | --- |
| Flechas | Girar |
| `+` / `−` | Acercar y alejar |
| `F` | Centrar el giro en la selección |
| `R` | Encuadrar todo |
| `1` … `4` | Isométrica, planta, norte, este |
| `P` | Perspectiva u ortográfica |
| `Esc` | Quitar la selección |

---

## 3. Definir el macizo rocoso

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

## 4. Geometría de la malla

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

## 5. Diseño de carga

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

## 6. Secuencia de salida

**Secuencia.** Hay tres formas de repartir los tiempos, y se eligen arriba del
panel.

### Vector de dirección

Es el método habitual con detonadores electrónicos y el más rápido de ajustar.
Se dibuja una flecha sobre la malla: dónde arranca el disparo y hacia dónde
avanza. El tiempo de cada taladro sale de su posición respecto de esa flecha.

**Colocarlo lleva dos clics.** Pulse **Colocar en el visor** (o `F9`), haga clic
en el punto de arranque y otro hacia donde avanza el disparo; entre ambos verá
la flecha siguiendo al cursor. `Esc` cancela.

Si no quiere dibujarla, **Automático** la deduce de la cara libre y del tamaño
de la malla, ya centrada y con la longitud justa. **Invertir sentido** hace que
la voladura salga por el lado contrario sin volver a trazarla. Azimut, ángulo y
longitud también se pueden escribir a mano.

| Parámetro | Qué hace |
| --- | --- |
| **BRB** | Milisegundos por metro **en la dirección de avance**: el alivio del burden. El rango habitual es 3 a 6 ms/m. Subirlo alarga el disparo y da más tiempo a que la roca se mueva. |
| **BRS** | Milisegundos por metro **en el sentido transversal**. En cero, cada fila sale entera a la vez; al subirlo la salida se abre en abanico y baja la carga operante. |
| **Ángulo** | Medido desde la vertical. 90° deja la flecha horizontal, que es lo normal en banco; por debajo, la secuencia progresa también en profundidad. |

### Patrón de amarre

El método clásico: retardo entre taladros de una fila y entre filas, con cinco
geometrías de propagación (fila por fila, V, echelon, eco y punto central).

### Punto central

La salida se abre radialmente desde un punto, a tantos milisegundos por metro.
Se coloca igual, con un clic sobre el visor.

---

## 7. Detonadores y plataformas

### Modelo de detonador

El modelo elegido no es un dato administrativo: fija el rango de tiempos
programables, el incremento mínimo y **la precisión real del disparo**. Entre un
electrónico de 0.005 % y un pirotécnico de 3 % hay dos órdenes de magnitud, y de
ahí sale la probabilidad de solape que se ve más abajo en el mismo panel.

Con **Ajustar los tiempos al incremento programable** activo, los retardos se
redondean a lo que el detonador sabe programar; así lo que se ve en pantalla es
lo que va a ocurrir en el terreno.

### Retardo entre plataformas

Seccionar la columna solo baja la vibración si cada tramo sale en un instante
distinto. **Entre plataformas** separa las cargas independientes del mismo
taladro, del fondo al collar; **entre cebos** separa los cebos de una misma
carga.

> Cuentan como cargas independientes las que están separadas por un taco o una
> cámara de aire. La carga de fondo y la columna que va encima son continuas:
> llevan un solo cebo y detonan juntas, así que el programa las trata como una.

### Comprobar antes de disparar

**Comprobar secuencia** valida el programa contra el detonador: tiempos fuera de
rango, valores que no se pueden programar, unidades por encima del máximo del
sistema, taladros con carga y sin cebo, y grupos que salen simultáneos sumando
su carga operante.

**Exportar a máquina** escribe el CSV con un detonador por carga independiente
—posición, identificador, tiempo, coordenadas, masa y producto— con la cabecera
del modelo y sus límites.

---

## 8. Simular el disparo

El panel de secuencia muestra la carga detonada por ventana de cooperación con
la línea de la carga máxima admisible para el límite de PPV declarado. Ninguna
barra debería superarla.

| Control | Para qué sirve |
| --- | --- |
| **Animar secuencia** (`F8`) | Reproduce el disparo sobre el visor 3D. |
| **Velocidad** | De 0.05x a 5x. Por debajo de 1x se ve en cámara lenta, que es como se aprecia el orden de salida. |
| **Isócronas** | Curvas de igual tiempo sobre la malla, cada N milisegundos. Donde se aprietan, la salida es lenta y el burden queda confinado; donde se abren, la voladura corre. |
| **Recorrido del disparo** | Une los collares en orden de salida: se ve de un vistazo si el amarre hace lo que se pretendía. |

---

## 9. Entorno y límites

**Diseño ▸ Entorno.**

1. Ubique el receptor sensible —vivienda, estructura, instrumento— con sus
   coordenadas reales.
2. Declare el PPV admisible (12.7 mm/s es el criterio USBM para vivienda con
   acabado de yeso), el límite de onda aérea y el radio de exclusión.
3. Ajuste las constantes de sitio `K` y `β`. **Los valores por defecto son
   genéricos**: sustitúyalos por la regresión de su propio monitoreo
   sismográfico en cuanto tenga registros.

---

## 10. Analizar

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

## 11. Tematizar el visor

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

## 12. Intervenir taladro por taladro

El panel **Propiedades** no es una ficha de consulta: es donde se edita el
taladro. Se abre al hacer clic sobre uno en el visor, en la tabla o en el
explorador.

### Clasificación

El desplegable **Tipo** cambia producción, precorte, recorte, amortiguado,
alivio, rainura o contorno. Cambia el color en el visor y las reglas de
revisión que se aplican. Con varios taladros seleccionados, **Aplicar tipo a
la selección** los reclasifica todos de una vez — que es como se marcan las
filas de precorte o los taladros amortiguados del contorno.

La misma operación está en la barra superior (*Asignar tipo*) y en el menú
**Selección ▸ Seleccionar por tipo**, que selecciona de golpe todos los
taladros de una clase.

### Geometría

Diámetro, longitud, subperforación, inclinación, azimut, cota de collar y
coordenadas se editan directamente. Sirve para corregir un taladro que salió
distinto en campo sin rehacer la malla completa.

### Retardo

Al escribir un retardo, ese taladro queda **fijado a mano** y el amarre
automático deja de recalcularlo. **Selección ▸ Liberar retardos fijados** lo
devuelve al patrón.

### Columna de carga

El editor muestra la columna real del taladro, del collar hacia el fondo. Cada
plataforma tiene su tipo —carga, taco o cámara de aire—, su longitud y, si es
carga, su producto, su acoplamiento y sus cebos. Debajo de cada una aparecen
la densidad lineal, los kilos y la presión sobre la pared.

- **Carga / Taco / Aire** agregan una plataforma por el collar.
- Las flechas mueven la plataforma hacia el collar o hacia el fondo.
- La línea de estado avisa si la columna no llena el taladro; el ajuste se
  hace sobre el taco de collar.

Editar la columna **desvincula el taladro de la regla global**: el panel de
Carga ya no lo pisa, y la tabla lo marca en la columna *Carga manual*.

- **Copiar a la selección** replica esa columna sobre todos los taladros
  seleccionados.
- **Volver a la regla global** descarta la carga manual y los recarga con el
  panel de Carga.

### Selección

| Cómo | Dónde |
| --- | --- |
| Clic, Ctrl + clic, Shift + clic | Visor 3D |
| Rectángulo | Botón de selección por ventana, o tecla `B` |
| Filas contiguas o sueltas | Tabla de taladros, con Shift y Ctrl |
| Todos los de una clase | Menú Selección ▸ Seleccionar por tipo |
| Todo, invertir, ninguno | `Ctrl+A`, `Ctrl+Shift+I`, `Ctrl+D` |

La selección es la misma en el visor, en la tabla y en el panel de
propiedades: lo que se marca en uno se refleja en los otros.

---

## 13. Optimizar

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

## 14. Importar datos reales

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

## 15. Entregables

| Acción | Resultado |
| --- | --- |
| **Reporte técnico** (`Ctrl+R`) | Documento HTML autocontenido con la memoria de cálculo completa, gráficos incrustados y el detalle de todos los taladros. Ábralo en el navegador e imprima a PDF. |
| **Exportar taladros** | CSV con coordenadas, carga, retardo, burden y factor de potencia por taladro, listo para el área de operaciones. |
| **Exportar a máquina** | Programa de tiempos con un detonador por carga independiente, para cargar en el sistema electrónico. |
| **Captura del visor** | PNG de la vista 3D actual. |
| **Guardar proyecto** (`Ctrl+S`) | Archivo `.xbp` con todo el diseño, incluida la topografía. |

---

## 16. Personalizar el programa

**Ver > Preferencias**, o `Ctrl+,`. Son 229 opciones repartidas en 17
categorías, con buscador arriba a la izquierda: escriba «burden», «clic» o
«chancado» y aparecen solo las opciones que hablan de eso.

| Categoría | Qué controla |
| --- | --- |
| **Apariencia** | Paleta base, color de acento y de cada superficie, colores de estado, tipografía y tamaños, densidad de la interfaz, radio de esquinas, estilo y tamaño de los iconos. |
| **Visor 3D** | Fondo y degradado, rejilla y rótulos, tríada y cubo de orientación, suavizado, sombreado, transparencia por capas, proyección e iluminación. |
| **Taladros** | Radio visual y resolución del cilindro, colores y opacidad del taco y de la cámara de aire, collares, etiquetas y su contenido, aspecto del resaltado de selección. |
| **Colores por tipo** | Un color por cada clase: producción, precorte, recorte, amortiguado, alivio, rainura y contorno. |
| **Interacción** | Modo de navegación, elevación máxima, velocidad de giro y de zoom, eje vertical invertido, selección con uno o dos clics, radio de captura, tolerancia de arrastre e intervalo de doble clic. |
| **Capas y terreno** | Color y opacidad de la topografía, su malla de alambre, la cara libre y el piso de banco. |
| **Animación** | Cuadros por segundo, velocidad, duración del destello y colores de pendiente, detonando y disparado. |
| **Campo de energía** | Tamaño de celda, radio de influencia, número de isosuperficies, opacidad y mapa de color. |
| **Gráficos** | Grosor de línea, rejilla, tamaño de fuente, resolución de exportación y los ocho colores de serie. |
| **Unidades y formato** | Sistema de unidades, separadores y decimales por magnitud. |
| **Diseño por defecto** | Los 39 valores con los que arranca un proyecto nuevo: perforación, malla, carguío, macizo y secuencia. |
| **Análisis** | P80 objetivo, umbral de sobretamaño, desviación de perforación, ventana de cooperación, simulaciones de dispersión, onda semilla y constantes de proyección y de onda aérea. |
| **Límites y normativa** | Receptor, umbrales de PPV y onda aérea, radio de exclusión, tipo de estructura y constantes de sitio. |
| **Costos** | Costos unitarios de perforación, accesorios, mano de obra, carguío, acarreo, chancado y voladura secundaria, con sus exponentes de sensibilidad. |
| **Optimización** | Rango de burden, número de pasos y relaciones S/B del barrido. |
| **Reportes** | Empresa, responsable, cargo, nota al pie y qué secciones incluir. |
| **Comportamiento** | Página de inicio al arrancar, malla de ejemplo, análisis automático, confirmación al salir, recientes y detalle de la bitácora. |

Los cambios se aplican al instante: un acento nuevo repinta la aplicación
entera, y tocar el aspecto de los taladros reconstruye la escena sin que haya
que regenerar la malla.

Cada opción tiene a su derecha un botón que la devuelve a su valor de fábrica, y
abajo están **Restablecer categoría** y **Restablecer todo**. Las opciones
marcadas con asterisco necesitan reiniciar.

**Exportar** guarda la configuración en un archivo JSON e **Importar** la
recupera: sirve para llevar el mismo entorno a otra máquina o para que todo el
equipo trabaje con los mismos costos y límites. En disco solo se guarda lo que
difiere del valor por defecto, así que el archivo se mantiene legible.

---

## 17. Antes de usarlo en producción

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
| `F9` | Colocar el vector de dirección |
| `Ctrl+,` | Preferencias |
| `Ctrl+A` · `Ctrl+D` · `Ctrl+Shift+I` | Seleccionar todo · quitar selección · invertir |
| `B` | Selección por ventana |

Con el foco en el visor: flechas para girar, `+` y `−` para acercar, `F`
centrar el giro en la selección, `R` encuadrar, `P` proyección, `Esc`
deseleccionar.
