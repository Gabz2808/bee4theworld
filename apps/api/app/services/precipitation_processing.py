from __future__ import annotations

import calendar
import math
from datetime import date

import pandas as pd

from app.services.gpm_imerg import GPMIMERGResult

QUALITY_OK = "ok"
QUALITY_PARTIAL_COVERAGE = "partial_coverage"
QUALITY_MISSING_VALUE = "missing_value"
QUALITY_MISSING_MONTH = "missing_month"


class PrecipitationProcessingError(ValueError):
    pass


def prepare_monthly_precipitation(
    result: GPMIMERGResult,
    start: date,
    end: date,
) -> pd.DataFrame:
    if start.day != 1:
        raise PrecipitationProcessingError("El inicio debe ser el primer día de un mes")
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        raise PrecipitationProcessingError("El final debe ser el último día de un mes")
    if end < start:
        raise PrecipitationProcessingError("La fecha final no puede preceder a la inicial")
    if result.output_units != "mm/month":
        raise PrecipitationProcessingError(
            f"Unidad de salida no compatible: {result.output_units!r}"
        )
    _monthly_unit_factor(result.source_units, start)

    expected_months = pd.date_range(start=start, end=end, freq="MS", name="month")
    records: dict[pd.Timestamp, tuple[float, float, str]] = {}
    for observation in result.monthly_values:
        if observation.month.day != 1:
            raise PrecipitationProcessingError(
                f"La fecha de observación {observation.month} no representa el inicio del mes"
            )
        month = pd.Timestamp(observation.month)
        if month not in expected_months:
            raise PrecipitationProcessingError(
                f"El mes {month:%Y-%m} está fuera del rango solicitado"
            )
        if month in records:
            raise PrecipitationProcessingError(
                f"Hay más de una observación para {month:%Y-%m}"
            )

        value = (
            float("nan")
            if observation.value is None
            else float(observation.value)
            * _monthly_unit_factor(result.source_units, observation.month)
        )
        coverage = float(observation.coverage_fraction)
        if not math.isnan(value) and not math.isfinite(value):
            raise PrecipitationProcessingError(
                f"El valor de precipitación no es finito para {month:%Y-%m}"
            )
        if math.isfinite(value) and value < 0:
            raise PrecipitationProcessingError(
                f"La precipitación no puede ser negativa para {month:%Y-%m}"
            )
        if not math.isfinite(coverage) or not 0 <= coverage <= 1:
            raise PrecipitationProcessingError(
                f"La cobertura debe estar entre 0 y 1 para {month:%Y-%m}"
            )
        if coverage == 0 and math.isfinite(value):
            raise PrecipitationProcessingError(
                f"Hay un valor de precipitación sin cobertura para {month:%Y-%m}"
            )

        if math.isnan(value):
            quality = QUALITY_MISSING_VALUE
        elif coverage < 1:
            quality = QUALITY_PARTIAL_COVERAGE
        else:
            quality = QUALITY_OK
        records[month] = (value, coverage, quality)

    frame = pd.DataFrame.from_dict(
        records,
        orient="index",
        columns=("precipitation_mm", "coverage_fraction", "quality_flag"),
    ).reindex(expected_months)
    frame.index.name = "month"
    missing_months = frame["quality_flag"].isna()
    frame.loc[missing_months, "coverage_fraction"] = 0.0
    frame.loc[missing_months, "quality_flag"] = QUALITY_MISSING_MONTH
    frame["precipitation_mm"] = pd.to_numeric(frame["precipitation_mm"])
    frame["coverage_fraction"] = frame["coverage_fraction"].astype(float)

    frame.attrs.update(
        {
            "dataset": result.dataset,
            "version": result.version,
            "source_units": result.source_units,
            "output_units": result.output_units,
            "unit_conversion": result.unit_conversion,
            "conversion_factors_by_month": {
                month.strftime("%Y-%m"): _monthly_unit_factor(
                    result.source_units,
                    month.date(),
                )
                for month in expected_months
            },
            "region_geojson": result.region.model_dump(mode="json"),
            "granule_ids": list(result.granule_ids),
            "spatial_resolution_degrees": result.spatial_resolution_degrees,
            "weighting_method": result.weighting_method,
        }
    )
    return frame


def _monthly_unit_factor(units: str, month: date) -> float:
    normalized = units.lower().replace(" ", "").replace("**", "^")
    days = calendar.monthrange(month.year, month.month)[1]
    if normalized in {"mm", "mm/month", "mmmonth-1", "mmmonth^-1", "kgm-2"}:
        return 1.0
    if normalized in {"mm/hr", "mm/hour", "mmh-1", "mmh^-1", "mmhr-1"}:
        return days * 24.0
    if normalized in {"mm/day", "mmd-1", "mmd^-1"}:
        return float(days)
    if normalized in {"kgm-2s-1", "kgm^-2s^-1", "kg/m^2/s"}:
        return days * 24.0 * 60.0 * 60.0
    raise PrecipitationProcessingError(
        f"Unidad de precipitation no reconocida: {units!r}; no se convertirá implícitamente"
    )


def aggregate_annual_precipitation(frame: pd.DataFrame) -> pd.DataFrame:
    if "precipitation_mm" not in frame.columns:
        raise PrecipitationProcessingError(
            "La serie debe incluir la columna precipitation_mm"
        )
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise PrecipitationProcessingError(
            "La serie debe usar un índice DatetimeIndex mensual"
        )
    if frame.index.has_duplicates:
        raise PrecipitationProcessingError("La serie contiene meses duplicados")

    annual_records: list[dict[str, int | float]] = []
    for year in sorted(frame.index.year.unique()):
        expected_months = pd.date_range(
            start=date(int(year), 1, 1),
            periods=12,
            freq="MS",
        )
        year_values = frame.loc[
            frame.index.year == year,
            "precipitation_mm",
        ].sort_index()
        if not year_values.index.equals(expected_months):
            continue

        try:
            values = year_values.astype(float).tolist()
        except (TypeError, ValueError) as error:
            raise PrecipitationProcessingError(
                f"Los valores de precipitación no son numéricos para {year}"
            ) from error

        if any(math.isnan(value) for value in values):
            continue
        if not all(math.isfinite(value) for value in values):
            raise PrecipitationProcessingError(
                f"Los valores de precipitación no son finitos para {year}"
            )
        if any(value < 0 for value in values):
            raise PrecipitationProcessingError(
                f"La precipitación no puede ser negativa para {year}"
            )

        annual_records.append(
            {
                "year": int(year),
                "annual_precipitation_mm": sum(values),
                "months_reported": 12,
            }
        )

    annual = pd.DataFrame.from_records(
        annual_records,
        columns=("year", "annual_precipitation_mm", "months_reported"),
    ).set_index("year")
    annual["annual_precipitation_mm"] = annual[
        "annual_precipitation_mm"
    ].astype(float)
    annual["months_reported"] = annual["months_reported"].astype(int)
    annual.attrs.update(frame.attrs)
    annual.attrs["annual_aggregation_rule"] = (
        "Solo se suman años calendario con 12 meses y 12 valores mensuales "
        "finitos; la cobertura espacial parcial se conserva y no excluye el año."
    )
    return annual
