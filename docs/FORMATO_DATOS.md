# Formato de los archivos de datos

Los importadores de X-BLAST son tolerantes: detectan solos el **delimitador**
(`;`, `,`, tabulador o `|`), la **codificación** (UTF-8, UTF-8 con BOM o
Latin-1) y los **nombres de columna** entre un conjunto de sinónimos. En la
práctica, los archivos que salen del software de la mina se cargan sin
editarlos.

Los números aceptan tanto punto como coma decimal. Las filas sin coordenadas
válidas se descartan y se informan en la bitácora.

---

## 1. Taladros

Un solo importador cubre desde un listado simple de collares hasta un archivo
de perforación con geometría completa.

### Columnas reconocidas

| Campo | Sinónimos aceptados | Obligatorio |
| --- | --- | --- |
| Identificador | `ID`, `BHID`, `HOLE`, `HOLE_ID`, `TALADRO`, `NOMBRE`, `POZO` | No — se autogenera |
| Este | `X`, `XP`, `EAST`, `EASTING`, `XCOLLAR`, `ESTE`, `COORD_X` | **Sí** |
| Norte | `Y`, `YP`, `NORTH`, `NORTHING`, `YCOLLAR`, `NORTE`, `COORD_Y` | **Sí** |
| Cota de collar | `Z`, `ZP`, `ELEV`, `ZCOLLAR`, `COTA`, `ELEV COLLAR` | No — 0 por defecto |
| Cota de fondo | `ELEV TOE`, `ELEVTOE`, `ZTOE`, `COTA FONDO` | No |
| Longitud | `LENGTH`, `LONGITUD`, `DEPTH`, `PROF`, `LARGO` | No |
| Azimut | `AZ`, `AZIMUTH`, `AZIMUT`, `RUMBO` | No — 0 por defecto |
| Buzamiento | `DIP`, `INCLINACION`, `BUZAMIENTO` | No — vertical por defecto |
| Diámetro | `DIAM`, `DIAMETER`, `DIAMETRO` | No — el del diseño |
| Material | `MATERIAL`, `TIPO`, `LITOLOGIA` | No |

### Cómo se completa lo que falta

- **`LENGTH` en cero o ausente** — el caso habitual de las exportaciones de
  campo: la longitud se calcula como `|Z_collar − Z_fondo| / sen(dip)`. La
  bitácora informa en cuántas filas se dedujo.
- **`DIP` negativo o positivo**: se acepta cualquier convención; se toma el
  valor absoluto acotado a 1–90°, donde 90 es vertical.
- **Sin `LENGTH` ni `ELEV TOE`**: se usa la longitud del diseño vigente.
- **Fila y columna de malla**: se deducen agrupando los collares por bandas
  según la dirección principal de la nube de puntos.

### Ejemplo — collares simples

```csv
BHID;XCOLLAR;YCOLLAR;ZCOLLAR
DH101;8075.3;6634.7;387.1
DH102;8026.0;6625.2;385.0
```

### Ejemplo — perforación completa

```csv
 ID; EAST; NORTH;ELEV TOE; ELEV COLLAR; LENGTH; AZ; DIP; MATERIAL
289;551021.94;64721.78;3415;3430;0;0;-90;Blasthole
290;551014.31;64724.22;3415;3430;0;0;-90;Blasthole
```

Aquí `LENGTH` viene en cero: X-BLAST deduce 15 m de la diferencia de cotas.

---

## 2. Topografía

Nube de puntos que se tría por Delaunay para generar la superficie y para
apoyar los collares sobre el terreno.

| Campo | Sinónimos | Obligatorio |
| --- | --- | --- |
| Este | `XP`, `X`, `EAST`, `ESTE` | **Sí** |
| Norte | `YP`, `Y`, `NORTH`, `NORTE` | **Sí** |
| Cota | `ZP`, `Z`, `ELEV`, `COTA` | **Sí** |

Las columnas adicionales (`PVALUE`, `PTN`, códigos de levantamiento) se
ignoran. Se requieren al menos tres puntos válidos.

```csv
PVALUE;PTN;XP;YP;ZP
1;1;8209.6;6200.0;381.0
1;2;8184.4;6254.2;381.0
```

La interpolación es lineal sobre la triangulación; fuera del dominio triangulado
se usa el vecino más próximo, de modo que un collar ligeramente fuera de la
nube no queda sin cota.

---

## 3. Conjuntos de ejemplo

La carpeta [`data/`](../data/) trae tres archivos reales:

| Archivo | Contenido |
| --- | --- |
| `datos TURPO.csv` | 228 taladros de producción con geometría completa |
| `Coordenadas.csv` | 12 collares simples |
| `Topografia.csv` | 358 puntos de levantamiento topográfico |

---

## 4. Salidas

### Proyecto — `.xbp`

JSON legible y versionable con el diseño completo: geometría, macizo, carga
por plataformas, secuencia, restricciones, costos, todos los taladros y —
opcionalmente — la topografía incrustada.

### Tabla de taladros — CSV

Separador `;` y codificación UTF-8 con BOM, para que Excel en español lo abra
directamente:

```
ID;ESTE;NORTE;COTA_COLLAR;COTA_FONDO;LONGITUD_M;DIAMETRO_MM;DIP;AZIMUT;
TACO_M;CARGA_KG;EXPLOSIVO;CEBOS;RETARDO_MS;BURDEN_M;ESPACIAMIENTO_M;
VOLUMEN_M3;FACTOR_POTENCIA;X50_CM;TIPO
```

### Reporte técnico — HTML

Documento autocontenido: los gráficos van incrustados como imágenes en base64
y no hay ninguna referencia externa, así que puede enviarse por correo o
archivarse tal cual. Incluye hoja de estilo de impresión para exportarlo a PDF
desde el navegador.
