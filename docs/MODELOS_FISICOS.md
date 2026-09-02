# Modelos físicos y matemáticos

Formulaciones implementadas en `xblast/core/`, con la referencia original y el
módulo donde vive cada una. Todas las unidades son SI salvo indicación expresa.

---

## 1. Caracterización del macizo — `core/models.py`

### Índice de volabilidad de Lilly (1986)

```
BI = 0.5 · (RMD + JPS + JPA + RDI + HF)
```

| Componente | Significado | Valores |
| --- | --- | --- |
| `RMD` | Descripción del macizo | 10 friable · 20 diaclasado en bloques · 25 diaclasado vertical · 50 masivo |
| `JPS` | Espaciamiento de discontinuidades | 10 (< 0.1 m) · 20 (0.1–0.3 m) · 25 (0.3–1.0 m) · 50 (> 1.0 m) |
| `JPA` | Orientación respecto a la cara | 20 buza hacia dentro · 30 rumbo perpendicular · 40 buza hacia fuera |
| `RDI` | Influencia de la densidad | `25·SG − 50` |
| `HF` | Factor de dureza | `E/3` si `E < 50 GPa`, si no `UCS/5` |

### Factor de roca de Kuz-Ram (Cunningham, 1987)

```
A = 0.06 · (RMD + JPS + JPA + RDI + HF) = 0.12 · BI
```

Valores típicos: 4–6 roca media, 7–10 dura, 10–13 muy dura. El motor lo acota
al rango 0.8–22.

---

## 2. Dimensionamiento de la malla — `core/pattern.py`

| Método | Formulación |
| --- | --- |
| **Konya-Walter (1972)** | `B = 0.012 · (2·SGe/SGr + 1.5) · De` con `De` en mm |
| **Langefors-Kihlström (1963)** | `B_max = (d/33) · √( ρe·s / (c·f·(S/B)) )` |
| **Ash (1963)** | `B = Kb · De`, con `Kb` = 20–32 según la resistencia de la roca |
| **Pearse** | `B = k · De · √(Pd / UCS)` |

`recommend_geometry()` descarta los valores atípicos por desviación absoluta
mediana, promedia el resto y fuerza `H/B ≥ 2`. Complementa con las reglas de
Konya: taco `T = 0.7·B` y subperforación `J = 0.3·B`.

### Relaciones de control

| Relación | Rango recomendado | Consecuencia fuera de rango |
| --- | --- | --- |
| `H/B` (rigidez) | ≥ 3 (mínimo 2) | Banco rígido: fragmentación gruesa, sobre-rotura, proyección |
| `S/B` | 1.0 – 1.8 | Bolones entre taladros o sobre-perforación |
| `T/B` (taco) | 0.5 – 1.2 | Flyrock y onda aérea, o bolones en la cresta |
| `J/B` (subperforación) | 0.15 – 0.50 | Lomos en el piso, o daño al banco inferior |
| `B/D` | 20 – 40 | Energía insuficiente en el frente, o sobre-consumo |

---

## 3. Burden real y alivio — `core/burden.py`

El burden nominal es un parámetro de diseño; el que gobierna la rotura es el
**burden real** de cada taladro.

- **Burden geométrico**: menor entre la distancia a la cara libre y la
  distancia al taladro más próximo situado hacia la cara.
- **Burden de alivio**: distancia al vecino que detona al menos 5 ms antes;
  ese hueco actúa como cara libre en el instante del disparo.
- **Volumen de responsabilidad**: teselación de Voronoi de los collares,
  recortada contra la envolvente convexa dilatada media malla, multiplicada
  por la altura de banco. Reemplaza el producto `B·S·H` uniforme y hace que el
  factor de potencia local sea real.
- **Confinamiento**: distancia relativa a la cara libre, normalizada; alimenta
  la predicción de proyección y de onda aérea.

---

## 4. Columna de carga — `core/charging.py`

### Densidad lineal

```
q = π · (D · c)² / 4 · ρe        [kg/m]
```

con `D` el diámetro del taladro y `c` el acoplamiento (`d_carga / d_taladro`).

### Presión de detonación y de pared

```
Pd = ρe · VOD² / 4                       [Pa]
Pw = Pd · 0.5 · c^2.6
```

El exponente 2.6 del desacoplamiento es la razón por la que una carga
desacoplada reduce drásticamente el daño a la pared en voladura de contorno.

### Taco mínimo

`T ≥ 22·D`, corregido por el factor de retención del material (grava chancada
retiene mejor que detritus o arena).

---

## 5. Secuencia — `core/timing.py`

### Tiempos de alivio

| Criterio | Rango recomendado |
| --- | --- |
| Entre taladros de una fila | 3 – 6 ms por metro de espaciamiento |
| Entre filas | 10 – 30 ms por metro de burden |

Por debajo del mínimo las cargas quedan confinadas —vibración alta y
fragmentación pobre—; por encima se pierde la interacción entre cargas y
aumenta el riesgo de corte de línea.

### Carga operante (MIC)

Ventana deslizante de 8 ms (regla de la USBM): las cargas que detonan dentro
de esa ventana cooperan sísmicamente y su masa se suma para predecir el PPV.

### Dispersión

| Sistema | Coeficiente de variación del retardo |
| --- | --- |
| Electrónico | 0.02 % |
| Pirotécnico (NONEL) | 3 % |
| Cordón detonante | 6 % |

`overlap_probability()` perturba los retardos con ese coeficiente en 400
realizaciones de Monte Carlo y devuelve la probabilidad de solape y de salida
fuera de secuencia.

---

## 6. Fragmentación — `core/fragmentation.py`

### Tamaño medio (Kuznetsov-Cunningham)

```
x50 = A · (V0/Qe)^0.8 · Qe^(1/6) · (115/RWS)^(19/30)     [cm]
```

`V0` es el volumen de responsabilidad del taladro y `Qe` su masa de explosivo.

### Índice de uniformidad (Cunningham, 1987; revisión 2005)

```
n = (2.2 − 14·B/d) · √((1 + S/B)/2) · (1 − W/B)
    · (|BCL − CCL| / Lc + 0.1)^0.1 · (Lc/H)
```

con `B` en metros, `d` en milímetros, `W` la desviación de perforación, `BCL`
y `CCL` las longitudes de carga de fondo y de columna, `Lc` la longitud
cargada y `H` la altura de banco. La malla al tresbolillo aporta un 10 % de
uniformidad adicional.

### Corrección por tiempo de alivio

El óptimo práctico está entre 3 y 6 ms/m. Fuera de ese rango `x50` crece hasta
un 18 % y `n` cae hasta un 15 %.

### Curva de Swebrec — KCO (Ouchterlony, 2005)

```
P(x) = 1 / (1 + [ ln(xmax/x) / ln(xmax/x50) ]^b )
b    = 2 · ln2 · ln(xmax/x50) · n
```

Sustituye a Rosin-Rammler porque respeta el tamaño máximo físico `xmax`
—impuesto por el bloque in situ y por el burden— y no sobreestima los finos.
La curva global de la voladura es la mezcla de las curvas por taladro
ponderada por el volumen de cada uno.

---

## 7. Vibraciones — `core/vibration.py`

### Campo lejano: distancia escalada

```
SD  = D / √W                 (raíz cuadrada, la habitual en voladura de banco)
PPV = K · SD^(−β)            [mm/s]
```

`K` y `β` son constantes de sitio que deben calibrarse con regresión sobre
registros sismográficos propios. La inversa `max_charge_for_ppv()` entrega la
carga operante máxima admisible para un límite dado.

### Campo cercano: Holmberg-Persson (1979)

```
PPV = K · [ q · ∫₀^L dz / R^(β/α) ]^α
```

Integra la carga distribuida a lo largo de la columna. Es el modelo válido
cuando la distancia es comparable a la longitud de carga, es decir para
evaluar el daño al talud remanente.

### Umbral de daño

```
PPV_c = σt · Vp / E          con σt ≈ UCS/12
```

Se reportan tres niveles: fisuración incipiente (0.25·PPV_c), fisuración
(PPV_c) y fracturamiento (4·PPV_c).

### Superposición de onda semilla

La respuesta de un taladro aislado se modela como sinusoide amortiguada
normalizada. La historia temporal del disparo completo es la suma lineal de
esa onda escalada por el PPV individual de cada taladro y desplazada por su
tiempo real de detonación. El máximo del registro es el PPV predicho — y es lo
que permite optimizar la secuencia contra un límite de vibración.

### Normativa

- **USBM RI8507 / OSMRE**: límite dependiente de la frecuencia (12.7 mm/s
  entre 4 y 15 Hz para vivienda con acabado de yeso, subiendo a 50.8 mm/s
  sobre 40 Hz).
- **DIN 4150-3**: por tipo de edificación (industrial, residencial, sensible)
  y frecuencia.

---

## 8. Onda aérea — `core/airblast.py`

```
P  = K · (D / W^(1/3))^(−a)          [kPa]
dB = 20 · log₁₀(P / 2·10⁻⁵)
```

`K` refleja el confinamiento (Siskind, 1980): 0.1 carga bien confinada, 3.3
voladura de producción normal, 185 carga desnuda al aire. Se corrige por:

- **taco**: por debajo de 20 diámetros el nivel sube 0.55 dB por diámetro
  faltante;
- **material de taco**: la grava chancada resta hasta 4 dB frente al detritus;
- **atmósfera**: +6 dB con inversión térmica, hasta +10 dB con viento hacia el
  receptor.

---

## 9. Proyección de rocas — `core/airblast.py`

| Mecanismo | Formulación |
| --- | --- |
| Reventón de cara | `Lmax = (k²/g) · (√q / B)^2.6` |
| Cráteres por taco | `Lmax = (k²/g) · (√q / T)^2.6` |
| Cota superior | Lundborg (1975): `Lmax = 260 · d^(2/3)` con `d` en pulgadas |

`q` es la densidad lineal de carga en kg/m, `B` el burden de alivio y `T` el
taco. La constante `k` de Richards & Moore (2004) vale 13.5 en condiciones
normales y hasta 27 en el peor caso. La distancia segura recomendada aplica un
factor de 1.5 sobre el alcance máximo.

---

## 10. Campo de energía — `core/energy.py`

Cada plataforma de carga se discretiza en elementos; cada elemento reparte su
energía sobre una grilla regular con un núcleo de soporte compacto tipo
Wendland C2, normalizado en volumen. El resultado, en MJ/m³, conserva la
energía total del disparo y se compara contra la energía objetivo
`PF · e_explosivo` para clasificar el volumen en sub-energizado, en rango y
sobre-energizado.

---

## 11. Costos mina-planta — `core/costs.py`

El costo aguas abajo escala con el tamaño medio de fragmento:

```
C(x50) = C_ref · (x50 / x50_ref)^e
```

| Etapa | Exponente `e` |
| --- | --- |
| Carguío | 0.55 |
| Acarreo | 0.30 |
| Chancado | 0.75 |

Más la voladura secundaria, proporcional al porcentaje de sobretamaño. Es este
acoplamiento el que hace que el mínimo del costo total por tonelada no
coincida con el mínimo del costo de perforación y voladura.

---

## Referencias

1. Lilly, P. (1986). *An empirical method of assessing rock mass blastability.*
2. Cunningham, C.V.B. (1987). *Fragmentation estimations and the Kuz-Ram model — four years on.*
3. Cunningham, C.V.B. (2005). *The Kuz-Ram fragmentation model — 20 years on.*
4. Ouchterlony, F. (2005). *The Swebrec function: linking fragmentation by blasting and crushing.*
5. Konya, C.J. & Walter, E.J. (1972). *Rock Blasting and Overbreak Control.*
6. Langefors, U. & Kihlström, B. (1963). *The Modern Technique of Rock Blasting.*
7. Holmberg, R. & Persson, P.A. (1979). *Design of tunnel perimeter blasthole patterns to prevent rock damage.*
8. Siskind, D.E. et al. (1980). *Structure response and damage produced by airblast from surface mining.* USBM RI 8485.
9. Siskind, D.E. et al. (1980). *Structure response and damage produced by ground vibration.* USBM RI 8507.
10. Richards, A.B. & Moore, A.J. (2004). *Flyrock control — by chance or design.*
11. Lundborg, N. (1975). *The hazards of flyrock in rock blasting.*
12. DIN 4150-3 (2016). *Vibraciones en edificaciones — efectos sobre estructuras.*
