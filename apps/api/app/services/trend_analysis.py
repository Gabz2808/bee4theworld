from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd

from app.models.exploration import AnnualPrecipitation, TrendAnalysis

DEFAULT_CONFIDENCE_LEVEL = 0.95
DEFAULT_MIN_YEARS_FOR_TREND = 10


class TrendAnalysisError(ValueError):
    pass


def calculate_climatology_and_anomalies(
    monthly_frame: pd.DataFrame,
    *,
    baseline_start_year: int | None = None,
    baseline_end_year: int | None = None,
) -> pd.DataFrame:
    """Calcula la media climatológica para cada mes del año (1 a 12)

    y computa la anomalía en mm (precipitación observada - media climatológica).
    """
    if "precipitation_mm" not in monthly_frame.columns:
        raise TrendAnalysisError(
            "El DataFrame mensual debe contener la columna 'precipitation_mm'"
        )
    if not isinstance(monthly_frame.index, pd.DatetimeIndex):
        raise TrendAnalysisError("El DataFrame mensual debe tener un DatetimeIndex")

    frame = monthly_frame.copy()

    # Seleccionar ventana de línea base si se especifica
    if baseline_start_year is not None or baseline_end_year is not None:
        mask = pd.Series(True, index=frame.index)
        if baseline_start_year is not None:
            mask &= frame.index.year >= baseline_start_year
        if baseline_end_year is not None:
            mask &= frame.index.year <= baseline_end_year
        baseline_slice = frame.loc[mask]
        if baseline_slice.empty:
            raise TrendAnalysisError(
                f"El período de línea base [{baseline_start_year}, {baseline_end_year}] "
                "no contiene observaciones en la serie temporal"
            )
    else:
        baseline_slice = frame

    # Media climatológica para cada uno de los 12 meses
    climatology = (
        baseline_slice.groupby(baseline_slice.index.month)["precipitation_mm"]
        .mean()
        .to_dict()
    )

    frame["climatology_mean_mm"] = frame.index.month.map(climatology).astype(float)
    frame["anomaly_mm"] = (
        frame["precipitation_mm"] - frame["climatology_mean_mm"]
    ).astype(float)

    frame.attrs.update(monthly_frame.attrs)
    frame.attrs["climatology_baseline"] = {
        "start_year": baseline_start_year,
        "end_year": baseline_end_year,
        "monthly_means": {
            month: round(val, 2) if pd.notna(val) else None
            for month, val in climatology.items()
        },
    }
    return frame


def calculate_theil_sen_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Calcula la pendiente de Sen (Theil-Sen estimator),

    que es la mediana de todas las pendientes entre pares de puntos (i < j).
    """
    n = len(y)
    if n < 2:
        raise TrendAnalysisError(
            "Se requieren al menos 2 puntos para estimar la pendiente"
        )

    i_idx, j_idx = np.triu_indices(n, k=1)
    dx = x[j_idx] - x[i_idx]
    zero_dx = dx == 0
    if np.any(zero_dx):
        raise TrendAnalysisError("Existen coordenadas temporales idénticas (dx = 0)")

    dy = y[j_idx] - y[i_idx]
    pairwise_slopes = dy / dx
    return float(np.median(pairwise_slopes))


def calculate_ols_trend(
    x: np.ndarray, y: np.ndarray
) -> tuple[float, float, float]:
    """Calcula la regresión lineal por mínimos cuadrados ordinarios (OLS).

    Retorna (slope, intercept, r_squared).
    """
    n = len(y)
    if n < 2:
        raise TrendAnalysisError(
            "Se requieren al menos 2 puntos para regresión lineal"
        )

    x_mean = np.mean(x)
    y_mean = np.mean(y)
    ss_xx = np.sum((x - x_mean) ** 2)
    if ss_xx == 0:
        raise TrendAnalysisError("Varianza en el eje temporal es cero")

    ss_xy = np.sum((x - x_mean) * (y - y_mean))
    slope = float(ss_xy / ss_xx)
    intercept = float(y_mean - slope * x_mean)

    ss_yy = np.sum((y - y_mean) ** 2)
    r_squared = float((ss_xy**2) / (ss_xx * ss_yy)) if ss_yy > 0 else 0.0

    return slope, intercept, r_squared


def calculate_lag1_autocorrelation(
    y: np.ndarray,
    x: np.ndarray | None = None,
    slope: float | None = None,
) -> float:
    """Calcula el coeficiente de autocorrelación serial de primer orden (lag-1 r1).

    Si se proporciona slope (y opcionalmente x), se calcula sobre los residuos
    desestacionalizados/sin tendencia (e_t = y_t - slope * x_t) según la metodología
    de Yue & Wang (2002) y USGS para evitar que la tendencia lineal infle artificialmente
    la autocorrelación.
    """
    n = len(y)
    if n < 3:
        return 0.0

    if slope is not None and x is not None and len(x) == n:
        residuals = y - slope * (x - x[0])
    elif slope is not None:
        residuals = y - slope * np.arange(n, dtype=float)
    else:
        residuals = y

    r_mean = float(np.mean(residuals))
    diff = residuals - r_mean
    denom = float(np.sum(diff ** 2))
    if denom <= 1e-12:
        return 0.0
    numer = float(np.sum(diff[:-1] * diff[1:]))
    return float(numer / denom)


def mann_kendall_test(
    y: np.ndarray,
    alpha: float = 0.05,
    *,
    r1: float | None = None,
    apply_autocorrelation_correction: bool = True,
) -> tuple[int, float, float, bool]:
    """Aplica la prueba no paramétrica de Mann-Kendall con corrección de empates

    y ajuste de varianza por dependencia serial (Modified Mann-Kendall según
    Hamed & Rao 1998 / Yue & Wang 2002 / USGS).

    Retorna:
    - s: estadístico de Mann-Kendall
    - var_s: varianza ajustada por empates y autocorrelación
    - p_value: valor p bilateral
    - is_significant: True si p_value < alpha, False en caso contrario.
    """
    n = len(y)
    if n < 3:
        raise TrendAnalysisError(
            "Se requieren al menos 3 observaciones para el test de Mann-Kendall"
        )

    i_idx, j_idx = np.triu_indices(n, k=1)
    dy = y[j_idx] - y[i_idx]
    s = int(np.sum(np.sign(dy)))

    # Corrección de varianza por valores empatados
    _, counts = np.unique(y, return_counts=True)
    ties = counts[counts > 1]
    tie_term = np.sum(ties * (ties - 1) * (2 * ties + 5))
    var_s = (n * (n - 1) * (2 * n + 5) - tie_term) / 18.0

    if var_s <= 0:
        # Varianza nula (todos los valores son idénticos)
        return s, 0.0, 1.0, False

    # Corrección por autocorrelación serial positiva lag-1 (Modified Mann-Kendall)
    if apply_autocorrelation_correction and n >= 4:
        if r1 is None:
            # Calcular pendiente de Theil-Sen preliminar para evaluar autocorrelación residual
            slopes = dy / (j_idx - i_idx)
            median_slope = float(np.median(slopes))
            r1 = calculate_lag1_autocorrelation(y, slope=median_slope)

        # Límites críticos de Anderson (1941) al 95% de confianza bilateral
        r_crit_upper = (-1.0 + 1.96 * math.sqrt(n - 2)) / (n - 1)
        if r1 > r_crit_upper and 0.0 < r1 < 1.0:
            # Factor de inflación de varianza de Hamed & Rao / Yue & Wang para AR(1)
            eta = 1.0 + (2.0 * r1 / (n * ((1.0 - r1) ** 2))) * (
                n * (1.0 - r1) - (1.0 - (r1 ** n))
            )
            eta = max(1.0, min(float(eta), 10.0))
            var_s *= eta

    std_s = math.sqrt(var_s)
    if s > 0:
        z = (s - 1) / std_s
    elif s < 0:
        z = (s + 1) / std_s
    else:
        z = 0.0

    # Probabilidad acumulada de la distribución normal estándar: Phi(z) = 0.5 * (1 + erf(z / sqrt(2)))
    phi_abs_z = 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0)))
    p_value = 2.0 * (1.0 - phi_abs_z)
    p_value = max(0.0, min(1.0, float(p_value)))

    is_significant = bool(p_value < alpha)
    return s, float(var_s), p_value, is_significant


def analyze_annual_trend(
    annual_data: Sequence[AnnualPrecipitation] | pd.DataFrame,
    *,
    min_years: int = DEFAULT_MIN_YEARS_FOR_TREND,
    confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
) -> TrendAnalysis:
    """Evalúa la tendencia de precipitación sobre la serie de acumulados anuales

    y emite un veredicto formal de TrendAnalysis (conclusive o inconclusive).
    """
    if isinstance(annual_data, pd.DataFrame):
        if "annual_precipitation_mm" not in annual_data.columns:
            raise TrendAnalysisError(
                "El DataFrame anual debe contener 'annual_precipitation_mm'"
            )
        years = np.array(annual_data.index if "year" not in annual_data.columns else annual_data["year"], dtype=float)
        values = np.array(annual_data["annual_precipitation_mm"], dtype=float)
    else:
        years = np.array([item.year for item in annual_data], dtype=float)
        values = np.array([item.annual_precipitation_mm for item in annual_data], dtype=float)

    # Filtrar valores finitos
    valid_mask = np.isfinite(years) & np.isfinite(values)
    years = years[valid_mask]
    values = values[valid_mask]

    method_name = "Sen's slope estimator & Mann-Kendall test"

    # Codex (Manuel): no tratar años separados como observaciones consecutivas de lag-1.
    if len(years) > 1:
        order = np.argsort(years)
        years, values = years[order], values[order]
        if np.any(np.diff(years) != 1):
            return TrendAnalysis(
                status="inconclusive", method=method_name, slope=None, slope_unit=None,
                p_value=None, is_significant=None, confidence_level=None,
                summary="La serie anual tiene años faltantes o duplicados; la tendencia es inconclusa.",
                methodological_note="La autocorrelación de primer orden requiere años consecutivos; revise la cobertura antes de interpretar la tendencia.",
            )

    # Regla 0: Sin años completos observados
    if len(values) == 0:
        return TrendAnalysis(
            status="not_computed",
            method=method_name,
            slope=None,
            slope_unit=None,
            p_value=None,
            is_significant=None,
            confidence_level=None,
            summary="Análisis de tendencia no calculado debido a falta de años calendario completos.",
            methodological_note=(
                "El rango temporal seleccionado no contiene años calendario completos con 12 meses observados."
            ),
        )

    # Regla 1: Datos insuficientes para representatividad climática
    if len(values) < min_years:
        return TrendAnalysis(
            status="inconclusive",
            method=method_name,
            slope=None,
            slope_unit=None,
            p_value=None,
            is_significant=None,
            confidence_level=None,
            summary=f"Serie temporal insuficiente ({len(values)} años) para evaluar tendencias climáticas anuales con representatividad estadística.",
            methodological_note=(
                f"Se requieren al menos {min_years} años calendario completos para evaluar "
                f"tendencias con representatividad estadística y distinguir tendencias de oscilaciones "
                f"multianuales o decil (como El Niño-Oscilación del Sur). La serie contiene {len(values)} año(s)."
            ),
        )

    # Regla 2: Serie constante (varianza cero)
    if np.all(values == values[0]):
        return TrendAnalysis(
            status="inconclusive",
            method=method_name,
            slope=None,
            slope_unit=None,
            p_value=None,
            is_significant=None,
            confidence_level=None,
            summary="No es posible evaluar la tendencia debido a varianza nula en las observaciones.",
            methodological_note="Todos los valores anuales registrados son idénticos.",
        )

    # Cálculo no paramétrico robusto
    slope = calculate_theil_sen_slope(years, values)

    # Regla 3: Autocorrelación residual severa que invalida los supuestos de independencia
    r1 = calculate_lag1_autocorrelation(values, x=years, slope=slope)
    if r1 >= 0.60:
        return TrendAnalysis(
            status="inconclusive",
            method=method_name,
            slope=None,
            slope_unit=None,
            p_value=None,
            is_significant=None,
            confidence_level=None,
            summary=(
                f"La serie presenta una fuerte dependencia temporal serial en sus residuos (r₁ = {r1:.2f}) "
                "que invalida el supuesto de observaciones independientes del análisis de tendencias."
            ),
            methodological_note=(
                f"Autocorrelación serial residual severa detectada (r₁ = {r1:.2f} >= 0.60). "
                "Según pautas de USGS (SIR 2004-5080), una persistencia temporal residual elevada infla "
                "la varianza y produce tasas inaceptables de falsos positivos en Mann-Kendall. "
                "Se requiere una serie temporal más extensa o modelos autorregresivos avanzados."
            ),
        )

    alpha = 1.0 - confidence_level
    _, _var_s_adjusted, p_value, is_significant = mann_kendall_test(
        values, alpha=alpha, r1=r1, apply_autocorrelation_correction=True
    )

    # Redondeo para presentación científica clara
    rounded_slope = round(slope, 2)
    rounded_p_value = round(p_value, 4)

    if is_significant:
        direction = "positiva (incremento)" if slope > 0 else "negativa (reducción)"
        summary = (
            f"Se detecta una tendencia {direction} estadísticamente significativa de "
            f"{abs(rounded_slope):.2f} mm/año (p = {rounded_p_value:.4f} < {alpha:.2f}) "
            f"con un nivel de confianza del {int(confidence_level * 100)}%. "
            f"La significancia estadística describe la monotonicidad de la serie y no implica "
            f"por sí sola atribución causal ni relevancia práctica."
        )
    else:
        summary = (
            f"No se detecta una tendencia estadísticamente significativa (no se rechaza la hipótesis nula) "
            f"en el período evaluado (pendiente de Theil-Sen = {rounded_slope:+.2f} mm/año, p = {rounded_p_value:.4f} >= {alpha:.2f}, "
            f"nivel de confianza del {int(confidence_level * 100)}%). La evidencia estadística no es suficiente "
            f"para afirmar una dirección de cambio sistemática; este resultado no demuestra ausencia de cambio "
            f"ni autoriza inferir estabilidad o atribuciones no verificadas."
        )

    methodological_note = None
    if len(values) >= 4:
        r_crit_upper = (-1.0 + 1.96 * math.sqrt(len(values) - 2)) / (len(values) - 1)
        if r1 > r_crit_upper:
            methodological_note = (
                f"Autocorrelación serial residual lag-1 detectada (r₁ = {r1:.3f}); se aplicó la corrección de varianza "
                f"de Hamed-Rao / Yue-Wang para controlar el riesgo de falsos positivos según pautas de USGS."
            )

    return TrendAnalysis(
        status="conclusive",
        method=method_name,
        slope=rounded_slope,
        slope_unit="mm/year",
        p_value=rounded_p_value,
        is_significant=is_significant,
        confidence_level=confidence_level,
        summary=summary,
        methodological_note=methodological_note,
    )
