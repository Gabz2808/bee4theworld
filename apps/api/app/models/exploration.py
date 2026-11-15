from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from app.models.base import APIModel
from app.models.geojson import GeoJSONPolygon


class DateRange(APIModel):
    start: date
    end: date

    @model_validator(mode="after")
    def end_must_not_precede_start(self) -> "DateRange":
        if self.end < self.start:
            raise ValueError("La fecha final debe ser igual o posterior a la inicial")
        return self


class EffectiveSelection(APIModel):
    region_id: str
    region_name: str
    boundary_source: str
    boundary_version: str
    requested_period: DateRange
    effective_period: DateRange


class ExplorationRequest(APIModel):
    region_id: str | None = None
    region: GeoJSONPolygon | None = None
    variable_id: Literal["precipitation"] = "precipitation"
    start_date: date | None = None
    end_date: date | None = None
    date_range: DateRange | None = None
    temporal_resolution: Literal["monthly"] = "monthly"

    @model_validator(mode="after")
    def validate_request_fields(self) -> "ExplorationRequest":
        if not self.region_id and not self.region:
            raise ValueError("Debe especificarse 'region_id' o una geometría 'region'")

        # Normalizar fechas entre start_date/end_date y date_range
        if self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("La fecha final debe ser igual o posterior a la inicial")
        elif self.date_range is not None:
            self.start_date = self.date_range.start
            self.end_date = self.date_range.end
        else:
            raise ValueError("Deben especificarse 'start_date' y 'end_date' (o 'date_range')")

        return self


class ExplorationMetadata(APIModel):
    variable_name: str
    source: str
    dataset: str
    unit: str
    spatial_resolution: str
    temporal_resolution: str = "monthly"
    selection: EffectiveSelection | None = None
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_units: str | None = None
    unit_conversion: str | None = None
    weighting_method: str | None = None
    source_granule_ids: list[str] | None = None
    data_accessed_at: datetime | None = None
    cache_status: Literal["hit", "stored", "miss", "unavailable", "disabled"] = "disabled"


class TrendAnalysis(APIModel):
    status: Literal["conclusive", "inconclusive", "not_computed"]
    method: str
    slope: float | None = Field(default=None, allow_inf_nan=False)
    slope_unit: str | None = None
    p_value: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    is_significant: bool | None = None
    confidence_level: float | None = Field(
        default=None,
        gt=0,
        le=1,
        allow_inf_nan=False,
    )
    summary: str = Field(min_length=1)
    methodological_note: str | None = None

    @model_validator(mode="after")
    def fields_must_match_verdict(self) -> "TrendAnalysis":
        metrics = (
            self.slope,
            self.slope_unit,
            self.p_value,
            self.is_significant,
            self.confidence_level,
        )
        if self.status in ("inconclusive", "not_computed"):
            if any(metric is not None for metric in metrics):
                raise ValueError(
                    f"Un análisis {self.status} no debe publicar métricas de tendencia"
                )
            if not self.methodological_note:
                raise ValueError(
                    f"Un análisis {self.status} requiere una nota metodológica"
                )
        elif any(metric is None for metric in metrics):
            raise ValueError(
                "Un análisis concluyente requiere todas las métricas de tendencia"
            )
        return self


class TimeSeriesPoint(APIModel):
    date: date
    value: float | None = Field(allow_inf_nan=False)
    coverage_fraction: float = Field(ge=0, le=1, allow_inf_nan=False)
    quality_flag: Literal[
        "ok",
        "partial_coverage",
        "missing_value",
        "missing_month",
    ]
    anomaly_mm: float | None = Field(default=None, allow_inf_nan=False)


class AnnualPrecipitation(APIModel):
    year: int = Field(ge=1)
    annual_precipitation_mm: float = Field(ge=0, allow_inf_nan=False)
    months_reported: Literal[12]


class ScientificInterpretation(APIModel):
    headline: str = Field(
        ...,
        description="Titular sintético del diagnóstico para el usuario.",
    )
    narrative: str = Field(
        ...,
        description="Explicación en prosa accesible sobre el comportamiento de la precipitación observada.",
    )
    trend_verdict_plain_language: str = Field(
        ...,
        description="Traducción comprensible del análisis de Mann-Kendall / Sen para no científicos.",
    )
    anomaly_summary: str = Field(
        ...,
        description="Resumen de anomalías y contraste entre meses secos y húmedos.",
    )
    prudence_guidelines: list[str] = Field(
        default_factory=list,
        description="Directrices de prudencia científica, límites de atribución y contrastación.",
    )


class ExplorationResponse(APIModel):
    status: Literal["success"]
    metadata: ExplorationMetadata
    trend_analysis: TrendAnalysis
    interpretation: ScientificInterpretation | None = None
    timeseries: list[TimeSeriesPoint] = Field(min_length=1)
    annual_totals: list[AnnualPrecipitation]
