# Especificación de Formatos de Datos: PERVOL

Este documento describe la estructura y sintaxis esperada para los archivos de datos de perforación, topografía y coordenadas en **PERVOL / X-BLAST Enterprise**.

---

## 1. Formato TURPO (`datos TURPO.csv`)

El formato TURPO se utiliza para registrar taladros de perforación reales en minería superficial y subterránea, incluyendo la orientación tridimensional del pozo.

### Estructura de Columnas
- **Separador admitido**: Punto y coma (`;`) o coma (`,`).
- **Codificación**: UTF-8 o UTF-8 con BOM.

| Columna | Tipo | Descripción | Ejemplo |
|---------|------|-------------|---------|
| `ID` | Texto / Entero | Identificador único del taladro | `289` o `T-101` |
| `EAST` | Decimal (m) | Coordenada Este (X) del collar | `551021.94` |
| `NORTH` | Decimal (m) | Coordenada Norte (Y) del collar | `64721.78` |
| `ELEV TOE` | Decimal (m) | Elevación de fondo del taladro (Z) | `3415.00` |
| `ELEV COLLAR` | Decimal (m) | Elevación del collar del taladro (Z) | `3430.00` |
| `LENGTH` | Decimal (m) | Longitud perforada (si es 0, se autocalcula) | `15.00` |
| `AZ` | Decimal (°) | Azimut de perforación (0° = Norte) | `0.0` |
| `DIP` | Decimal (°) | Inclinación desde horizontal o vertical | `-90.0` |
| `MATERIAL` | Texto | Tipo de roca o función del tiro | `Blasthole` |

### Ejemplo
```csv
ID;EAST;NORTH;ELEV TOE;ELEV COLLAR;LENGTH;AZ;DIP;MATERIAL
289;551021.94;64721.78;3415;3430;15;0;-90;Blasthole
290;551024.94;64721.78;3415;3430;15;0;-90;Blasthole
```

---

## 2. Formato Topografía (`Topografia.csv`)

Nube de puntos topográficos para la interpolación de superficie del terreno y generación de la malla triangulada (Delaunay 3D).

### Estructura de Columnas
| Columna | Tipo | Descripción | Ejemplo |
|---------|------|-------------|---------|
| `PVALUE` | Entero | Código o identificador del punto | `1` |
| `PTN` | Texto / Entero | Número de punto | `100` |
| `XP` | Decimal (m) | Coordenada Este | `7950.25` |
| `YP` | Decimal (m) | Coordenada Norte | `6540.10` |
| `ZP` | Decimal (m) | Elevación / Cota | `390.45` |

### Ejemplo
```csv
PVALUE;PTN;XP;YP;ZP
1;1;7950.25;6540.10;390.45
1;2;7955.10;6542.30;391.20
```

---

## 3. Formato Coordenadas Simples (`Coordenadas.csv`)

Archivo simple para mallas regulares o importación rápida de pozos verticales.

```csv
ID,X,Y,Z,Profundidad,Diametro
T1,100.0,200.0,4000.0,12.0,165.0
T2,105.0,200.0,4000.0,12.0,165.0
```
