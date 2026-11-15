# Criterios Científicos de Tendencia, Cobertura e Interpretación (Backend 4/7 #18)

Este documento describe la base metodológica, supuestos estadísticos y salvaguardas científicas implementadas en el backend de Iyök para el análisis de tendencias climáticas, control de cobertura espacial y generación de narrativas verificables.

---

## 1. Longitud de Serie y Representatividad Climática

- **Umbral Mínimo:** Se establece un mínimo predeterminado de **10 años calendario completos** (`DEFAULT_MIN_YEARS_FOR_TREND = 10`) para declarar una tendencia como analizable (`conclusive`).
- **Justificación:** En ciencias de la Tierra y climatología (OMM, USGS), series anuales de 5 o 6 años son demasiado cortas para aislar tendencias climáticas de la variabilidad interanual (como fases ENSO de El Niño/La Niña). Períodos menores a 10 años devuelven automáticamente `status: "inconclusive"` con una nota metodológica que instruye ampliar la ventana temporal.

---

## 2. Cobertura Espacial Mensual y Acumulación Anual

- **Umbral Mínimo Mensual:** `DEFAULT_MIN_MONTHLY_COVERAGE = 0.70` (70%).
- **Regla de Acumulación:** La precipitación total anual solo se calcula si el año cuenta con los 12 meses observados y cada mes cumple con al menos un 70% de cobertura espacial dentro del polígono.
- **Prevención de Sesgos:** Sumar meses con baja cobertura espacial (< 70%) generaría un sesgo de subestimación artificial del acumulado anual que distorsionaría el cálculo de pendientes Sen y estadísticos Mann-Kendall.

---

## 3. Dependencia Temporal y Autocorrelación Serial (USGS / Yue & Wang)

La prueba no paramétrica de Mann-Kendall asume independencia estadística entre las observaciones sucesivas. La presencia de autocorrelación serial positiva ($r_1 > 0$) infla la varianza del estadístico $S$, aumentando erróneamente la tasa de falsos positivos (error Tipo I).

### 3.1. Evaluación sobre Residuos Desprovistos de Tendencia (Detrending)
Conforme a **Yue & Wang (2002)** y las directrices hidrológicas del **USGS (SIR 2004-5080)**, el coeficiente de autocorrelación lag-1 ($r_1$) no debe calcularse sobre las observaciones brutas, ya que una pendiente lineal pronunciada induce artificialmente un $r_1$ alto. Se calcula sobre los residuos:
$$e_t = y_t - \text{slope} \cdot x_t$$

### 3.2. Intervalo Crítico de Anderson (Ruido Blanco)
Para evaluar si $r_1$ difiere significativamente de cero al nivel de significancia del 5%, se emplean los límites de Anderson:
$$r_{\text{crit}} = \frac{-1 \pm 1.96 \sqrt{n - 2}}{n - 1}$$

### 3.3. Mann-Kendall Modificado (Varianza Inflada)
Si $r_1 > r_{\text{crit, upper}}$, se aplica el factor de corrección de varianza ($\eta = n / n^*$) derivado de Hamed & Rao (1998) y Yue & Wang (2002):
$$\text{Var}^*(S) = \text{Var}(S) \cdot \left[ 1 + \frac{2}{n(n-1)(n-2)} \sum_{k=1}^{n-1} (n - k)(n - k - 1)(n - k - 2) \cdot r_k \right]$$
Aproximado para lag-1 como:
$$\eta \approx 1 + 2 \cdot \frac{r_1^n - n \cdot r_1 + n - 1}{(n - 1) \cdot (1 - r_1)^2}$$
$$\text{Var}^*(S) = \text{Var}(S) \cdot \eta$$

### 3.4. Criterio de Inconclusividad por Dependencia Severa
Si la autocorrelación residual supera el umbral crítico de $r_1 \ge 0.60$, la serie viola de forma sustancial el supuesto de intercambiabilidad de Mann-Kendall y el análisis anual se etiqueta como `inconclusive`.

---

## 4. Prudencia en la Narrativa e Interpretación

En concordancia con `AGENTS.md` y `revision-respuesta-backend.md`:
1. **No rechazar $H_0$ ($p \ge 0.05$):** Jamás se afirma que la variación se deba a *"causas naturales"* o *"variabilidad natural"*, ni se interpreta como prueba concluyente de que el clima *"no está cambiando"*. Se redacta con rigor estadístico:
   > *"No se detecta una tendencia estadísticamente significativa (no se rechaza la hipótesis nula, p >= 0.05). Este resultado no demuestra ausencia de cambio ni autoriza atribuir la variación a causas no verificadas."*
2. **Rechazo de $H_0$ ($p < 0.05$):** Se evitan frases hiperbólicas como *"respaldo estadístico robusto"* o inferencias directas de causalidad climática o ecológica.
3. **Transición Instrumental de Sensores (2014):** Se documenta explícitamente en las pautas científicas que la serie IMERG combina TRMM (pre-2014) y GPM Core Observatory (2014 en adelante), advirtiendo que los cambios instrumentales pueden inducir artefactos de homogeneidad temporal.
