# Modelos Físicos y Matemáticos: PERVOL

Este documento recopila la base teórica y las formulaciones implementadas en el núcleo de cálculo (`VOLADURA_PRO_10X/core/` y `physics_engine.py`).

---

## 1. Modelo de Fragmentación Kuz-Ram

El modelo de Kuz-Ram predice la distribución granulométrica resultante de la voladura combinando la ecuación de tamaño medio de Cunningham con la función de distribución de Rosin-Rammler.

### Tamaño Medio de Fragmentos (\(X_m\))
\[
X_m = A \cdot Q^{-0.167} \cdot \left(\frac{Q_e}{Q}\right)^{0.63} \cdot \left(\frac{E_{RBS}}{115}\right)^{-0.63}
\]
Donde:
- \(A\): Factor de roca (típicamente entre 6 y 14 según RMR y estructura geológica).
- \(Q\): Masa de carga por taladro (\(\text{kg}\)).
- \(Q_e\): Factor de carga específico (\(\text{kg/m}^3\)).
- \(E_{RBS}\): Potencia relativa en volumen respecto al ANFO estándar (\(100\)).

### Índice de Uniformidad (\(n\))
\[
n = \left(2.2 - 14 \frac{B}{d}\right) \cdot \sqrt{\frac{1 + S/B}{2}} \cdot \left(1 - \frac{W}{B}\right) \cdot \left(\frac{L}{H}\right)
\]

### Función de Rosin-Rammler
La fracción pasante \(R(x)\) para un tamaño de malla \(x\) está dada por:
\[
R(x) = 1 - \exp\left[ -\left(\frac{x}{X_c}\right)^n \right]
\]
Donde \(X_c\) es la dimensión característica calculada a partir de \(X_m\).

---

## 2. Atenuación de Vibraciones (Holmberg-Persson)

Para evaluar el daño al macizo rocoso remanente y taludes, se implementa el modelo de carga cilíndrica continua de Holmberg & Persson (1979).

### Formulación de Campo Cercano
La velocidad pico de partícula (\(PPV\)) en un punto a distancia \(R\) se obtiene integrando la contribución a lo largo de la columna de carga:
\[
PPV = K \cdot \left( \int_{0}^{L} \frac{dz}{\left( r^2 + z^2 \right)^{\frac{\beta}{2\alpha}}} \right)^\alpha
\]
Donde:
- \(K, \alpha, \beta\): Constantes de sitio obtenidas por regresión sísmica.
- \(L\): Longitud de la carga explosiva.
- \(r\): Distancia radial mínima al eje del barreno.

### Regla de Carga Cooperante de 8 ms
Dos o más taladros que detonan con una diferencia de tiempo inferior a 8 milisegundos se consideran cargas cooperantes, sumando sus masas efectivas (\(Q_{max}\)) para el cálculo del daño sísmico en campo lejano:
\[
PPV = K \cdot \left(\frac{D}{\sqrt{Q_{max}}}\right)^{-\beta}
\]

---

## 3. Presión de Barreno y Desacoplamiento

Para voladura de contorno y precorte, se calcula la caída de presión de detonación debida al desacoplamiento espacial entre el cartucho explosivo y las paredes del taladro:
\[
P_b = \left( \frac{\rho_e \cdot VOD^2}{8} \right) \cdot \left( C^{0.5} \cdot \frac{\phi_e}{\phi_b} \right)^\gamma
\]
Donde:
- \(\rho_e\): Densidad del explosivo (\(\text{kg/m}^3\)).
- \(VOD\): Velocidad de detonación (\(\text{m/s}\)).
- \(\phi_e, \phi_b\): Diámetros de carga y barreno respectivamente.
- \(\gamma\): Exponente de expansión adiabática (\(2.4\) para barreno seco, \(1.8\) para barreno con agua).

---

## 4. Dispersión Estocástica y Análisis de Solapamiento

Los detonadores pirotécnicos (NONEL) presentan una variabilidad nominal descrita mediante una distribución gaussiana \(N(\mu, \sigma^2)\). La probabilidad de solapamiento entre dos taladros contiguos \(i\) y \(j\) (riesgo de corte de línea o detonación fuera de secuencia) se calcula evaluando:
\[
Z = \frac{(t_j - t_i) - \Delta t_{min}}{\sqrt{\sigma_i^2 + \sigma_j^2}}
\]
\[
P_{OSD} = \Phi(-Z)
\]
El sistema clasifica el riesgo en:
- **Verde (Bajo)**: \(P_{OSD} < 1\%\)
- **Amarillo (Medio)**: \(1\% \le P_{OSD} \le 5\%\)
- **Rojo (Alto)**: \(P_{OSD} > 5\%\)
