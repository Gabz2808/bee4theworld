from __future__ import annotations

import math
from typing import Sequence

import pandas as pd
from app.models.exploration import (
    AnnualPrecipitation,
    ExplorationMetadata,
    ScientificInterpretation,
    TrendAnalysis,
)

SPANISH_MONTH_NAMES = [
    "",
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


def format_month_label(month_num: int, year: int | None = None) -> str:
    name = SPANISH_MONTH_NAMES[month_num] if 1 <= month_num <= 12 else f"mes {month_num}"
    return f"{name} de {year}" if year else name


def generate_interpretation(
    metadata: ExplorationMetadata,
    trend_analysis: TrendAnalysis,
    frame_with_anomalies: pd.DataFrame,
    annual_totals: Sequence[AnnualPrecipitation] | pd.DataFrame,
) -> ScientificInterpretation:
    """Genera una interpretación científica en lenguaje natural accesible, riguroso y prudente,

    sustentada exclusivamente en los cálculos observados y las directrices metodológicas de Iyök.
    """
    region_name = (
        metadata.selection.region_name
        if metadata.selection and metadata.selection.region_name
        else "la región seleccionada"
    )
    dataset_name = metadata.dataset or "NASA GPM IMERG Final V07"

    # 1. Análisis de totales anuales
    if isinstance(annual_totals, pd.DataFrame):
        annual_records = [
            (int(row["year"]), float(row["annual_precipitation_mm"]))
            for _, row in annual_totals.iterrows()
            if pd.notna(row.get("annual_precipitation_mm"))
        ]
    else:
        annual_records = [
            (item.year, item.annual_precipitation_mm)
            for item in annual_totals
            if item.annual_precipitation_mm is not None
        ]

    num_years = len(annual_records)

    # 2. Análisis del régimen estacional y extremos mensuales observados
    valid_precip = frame_with_anomalies["precipitation_mm"].dropna()
    has_monthly_data = not valid_precip.empty

    if has_monthly_data:
        max_idx = valid_precip.idxmax()
        min_idx = valid_precip.idxmin()
        max_val = float(valid_precip.loc[max_idx])
        min_val = float(valid_precip.loc[min_idx])
        max_month_str = format_month_label(max_idx.month, max_idx.year)
        min_month_str = format_month_label(min_idx.month, min_idx.year)
        total_months = len(valid_precip)
    else:
        max_val, min_val = 0.0, 0.0
        max_month_str, min_month_str = "desconocido", "desconocido"
        total_months = 0

    # 3. Construcción del Titular (Headline)
    if trend_analysis.status == "conclusive":
        if trend_analysis.is_significant:
            direction = "incremento" if (trend_analysis.slope or 0) > 0 else "reducción"
            headline = f"Tendencia estadística significativa de {direction} detectada en la precipitación anual"
        else:
            headline = "Precipitación anual sin tendencia direccional estadísticamente significativa"
    elif trend_analysis.status == "inconclusive":
        headline = "Comportamiento pluviométrico observado con tendencia climática formalmente inconclusa"
    else:
        headline = "Registro pluviométrico mensual sin evaluación de tendencia anual"

    # 4. Narrativa de la serie observada
    narrative_parts: list[str] = []

    if num_years > 0:
        if num_years == 1:
            y, val = annual_records[0]
            narrative_parts.append(
                f"En {region_name}, la precipitación acumulada durante el año {y} alcanzó {val:.1f} mm/año, "
                f"estimada a partir de {total_months} meses calendario de observaciones satelitales calibradas ({dataset_name})."
            )
        else:
            vals = [val for _, val in annual_records]
            mean_val = sum(vals) / len(vals)
            min_y, min_y_val = min(annual_records, key=lambda x: x[1])
            max_y, max_y_val = max(annual_records, key=lambda x: x[1])
            narrative_parts.append(
                f"A lo largo de los {num_years} años analizados en {region_name}, el promedio anual de precipitación "
                f"fue de {mean_val:.1f} mm/año, fluctuando entre un mínimo de {min_y_val:.1f} mm en {min_y} "
                f"y un máximo de {max_y_val:.1f} mm en {max_y}."
            )
    elif total_months > 0:
        narrative_parts.append(
            f"Para {region_name}, se procesaron {total_months} meses calendario de mediciones satelitales ({dataset_name})."
        )

    if has_monthly_data:
        narrative_parts.append(
            f"El ciclo estacional mostró su pico de mayor precipitación en {max_month_str} ({max_val:.1f} mm/mes), "
            f"mientras que el período más seco correspondió a {min_month_str} ({min_val:.1f} mm/mes)."
        )

    narrative = " ".join(narrative_parts)

    # 5. Resumen de anomalías y contraste estacional
    anomaly_parts: list[str] = []
    if "anomaly_mm" in frame_with_anomalies.columns and not frame_with_anomalies["anomaly_mm"].dropna().empty:
        valid_anom = frame_with_anomalies["anomaly_mm"].dropna()
        if (valid_anom == 0).all() and num_years <= 1:
            anomaly_parts.append(
                "Al analizar un solo año calendario de registro, las anomalías calculadas respecto a la media de ese mismo año son nulas por definición. "
                "Para observar desviaciones reales (meses inusualmente húmedos o secos) se requiere contrastar contra una climatología multianual de referencia."
            )
        else:
            max_anom_idx = valid_anom.idxmax()
            min_anom_idx = valid_anom.idxmin()
            max_anom = float(valid_anom.loc[max_anom_idx])
            min_anom = float(valid_anom.loc[min_anom_idx])
            anomaly_parts.append(
                f"Respecto a la climatología base, la mayor anomalía positiva registrada ocurrió en {format_month_label(max_anom_idx.month, max_anom_idx.year)} "
                f"con {max_anom:+.1f} mm sobre el promedio esperado, mientras que el déficit más marcado se registró en "
                f"{format_month_label(min_anom_idx.month, min_anom_idx.year)} con {min_anom:+.1f} mm por debajo de la media."
            )
    else:
        anomaly_parts.append("No se registraron suficientes observaciones para cuantificar anomalías climatológicas.")

    anomaly_summary = " ".join(anomaly_parts)

    # 6. Traducción a lenguaje llano del veredicto de tendencia
    if trend_analysis.status == "conclusive":
        slope = trend_analysis.slope if trend_analysis.slope is not None else 0.0
        p_val = trend_analysis.p_value if trend_analysis.p_value is not None else 1.0
        unit = trend_analysis.slope_unit or "mm/año"

        if trend_analysis.is_significant:
            dir_str = "un aumento promedio" if slope > 0 else "una reducción promedio"
            trend_verdict = (
                f"La prueba estadística no paramétrica de Mann-Kendall confirma {dir_str} de {abs(slope):.2f} {unit} "
                f"(valor p = {p_val:.4f}, inferior al umbral de significancia de 0.05). "
                f"Esto indica que el patrón de cambio observado a lo largo de los {num_years} años tiene un respaldo estadístico "
                f"robusto y es altamente improbable que se deba a simple variabilidad aleatoria del muestreo."
            )
        else:
            trend_verdict = (
                f"Aunque el estimador robusto de Theil-Sen sugiere una variación nominal de {slope:+.2f} {unit}, "
                f"la prueba de Mann-Kendall arrojó un valor p = {p_val:.4f} (mayor al umbral de 0.05). "
                f"Por tanto, desde el punto de vista estadístico no se puede descartar que la variación sea fluctuación natural; "
                f"la serie no muestra una tendencia direccional consistente ni concluyente."
            )
    elif trend_analysis.status == "inconclusive":
        trend_verdict = (
            f"La serie disponible contiene {num_years} año(s) calendario completo(s). "
            f"En ciencias de la atmósfera y el clima, los ciclos naturales de corto y mediano plazo (como El Niño, La Niña o la Oscilación del Sur) "
            f"provocan oscilaciones interanuales marcadas. Afirmar una tendencia a largo plazo con menos de 5 años de datos "
            f"sería metodológicamente imprudente, pues se corre el riesgo de confundir una variación cíclica transitoria con una tendencia permanente."
        )
    else:
        trend_verdict = (
            "El rango de fechas consultado no contiene años calendario cerrados (12 meses completos), "
            "por lo que no es científicamente válido estimar tasas anuales de cambio."
        )

    # 7. Pautas de prudencia y rigor científico
    prudence_guidelines = [
        (
            "Correlación y tendencia no implican causalidad: Un cambio detectado en la precipitación no demuestra por sí solo "
            "atribución al cambio climático antropogénico ni a un evento específico sin estudios formales de modelación y atribución climática."
        ),
        (
            "Naturaleza de la medición satelital: El producto NASA GPM IMERG V07 combina mediciones de múltiples sensores de satélite "
            "con calibración mensual de pluviómetros. Al contar con una resolución espacial de 0.1° (~10 km), promedia áreas amplias y "
            "puede suavizar microclimas y lluvias orográficas locales en zonas montañosas o costeras."
        ),
        (
            "Contrastación en superficie: Para gestión operativa del agua o evaluación de riesgos locales, se recomienda contrastar "
            "estas estimaciones satelitales con estaciones meteorológicas en tierra del Instituto Meteorológico Nacional o entidades locales equivalentes."
        ),
    ]

    return ScientificInterpretation(
        headline=headline,
        narrative=narrative,
        trend_verdict_plain_language=trend_verdict,
        anomaly_summary=anomaly_summary,
        prudence_guidelines=prudence_guidelines,
    )
