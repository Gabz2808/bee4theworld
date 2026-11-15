from __future__ import annotations

import calendar
import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException

from app.core.cache import load_from_cache, save_to_cache, save_to_supabase
from app.models.catalog import (
    CatalogCombination,
    CatalogRegion,
    CatalogResponse,
    CatalogVariable,
)
from app.models.exploration import (
    AnnualPrecipitation,
    DateRange,
    EffectiveSelection,
    ExplorationMetadata,
    ExplorationRequest,
    ExplorationResponse,
    ScientificInterpretation,
    TimeSeriesPoint,
)
from app.models.geojson import GeoJSONPolygon
from app.models.regions import Region, RegionsResponse
from app.models.variables import AvailableInterval, Variable, VariablesResponse
from app.services.interpretation_service import generate_interpretation
from app.services.gpm_imerg import (
    DataIntegrityError,
    DataUnavailableError,
    GPMIMERGConnector,
    GPMIMERGError,
    GPMIMERGResult,
)
from app.services.precipitation_processing import (
    PrecipitationProcessingError,
    aggregate_annual_precipitation,
    prepare_monthly_precipitation,
)
from app.services.trend_analysis import (
    TrendAnalysisError,
    analyze_annual_trend,
    calculate_climatology_and_anomalies,
)

MIN_SUPPORTED_DATE = date(2001, 1, 1)
MAX_SUPPORTED_DATE = date(2024, 12, 31)

DEFAULT_COSTA_RICA_GEOM = GeoJSONPolygon(
    type="Polygon",
    coordinates=[
        [
            [-85.95, 10.05],
            [-85.55, 11.10],
            [-84.80, 11.00],
            [-83.60, 10.75],
            [-82.60, 9.55],
            [-82.85, 8.35],
            [-83.65, 8.50],
            [-84.90, 9.50],
            [-85.45, 9.85],
            [-85.95, 10.05],
        ]
    ],
)

DEFAULT_REGIONS = [
    Region(
        id="costa-rica-continental",
        name="Costa Rica Continental",
        description="Límite territorial continental de la República de Costa Rica según cartografía oficial.",
        boundary_source="Instituto Geográfico Nacional (IGN) / WDC",
        boundary_version="2024",
        geom=DEFAULT_COSTA_RICA_GEOM,
    )
]

DEFAULT_VARIABLES = [
    Variable(
        id="precipitation",
        name="Precipitación mensual estimada",
        source="NASA GPM IMERG Final Run (GPM_3IMERGM V07) vía GES DISC / Giovanni",
        unit="mm/month",
        available_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
    )
]


def get_default_regions() -> list[Region]:
    return list(DEFAULT_REGIONS)


def get_default_variables() -> list[Variable]:
    return list(DEFAULT_VARIABLES)


def get_catalog(supabase_client: Any | None = None) -> CatalogResponse:
    """Genera el catálogo unificado para GET /api/v1/catalog con regiones,

    variables, resoluciones temporales y combinaciones disponibles con cobertura real.
    """
    regions_list = [
        CatalogRegion(
            id=r.id,
            name=r.name,
            description=r.description,
            boundary_source=r.boundary_source,
            boundary_version=r.boundary_version,
            geom=r.geom,
        )
        for r in DEFAULT_REGIONS
    ]

    variables_list = [
        CatalogVariable(
            id="precipitation",
            name="Precipitación mensual estimada",
            source="NASA GES DISC / Giovanni",
            dataset="GPM_3IMERGM.07",
            unit="mm/month",
            spatial_resolution="0.1° (~10 km); promedio ponderado espacial",
            temporal_resolution="monthly",
            available_interval=AvailableInterval(
                start=MIN_SUPPORTED_DATE,
                end=MAX_SUPPORTED_DATE,
            ),
            restrictions=[
                "Requiere fechas alineadas a mes completo (primer día a último día de mes).",
                "Estimación satelital combinada con pluviómetros; no sustituye estaciones puntuales.",
            ],
        )
    ]

    combinations = [
        CatalogCombination(
            region_id="costa-rica-continental",
            variable_id="precipitation",
            available_interval=AvailableInterval(
                start=MIN_SUPPORTED_DATE,
                end=MAX_SUPPORTED_DATE,
            ),
            temporal_resolution="monthly",
            is_ready_for_exploration=True,
            notes="Serie continua de 288 meses calendario verificados en CMR/IMERG.",
        )
    ]

    return CatalogResponse(
        status="success",
        regions=regions_list,
        variables=variables_list,
        combinations=combinations,
    )


def resolve_region(
    request: ExplorationRequest,
    supabase_client: Any | None = None,
) -> tuple[GeoJSONPolygon, str, str, str, str]:
    """Resuelve la geometría y metadatos de la región a partir de region_id o polígono directo.

    Retorna: (geom, region_id, region_name, boundary_source, boundary_version)
    """
    if request.region_id:
        if supabase_client is not None:
            try:
                query = supabase_client.table("regions").select("id, name, boundary_source, boundary_version, geom")
                if request.region_id in ("costa-rica-continental", "costa-rica"):
                    query = query.eq("name", "Costa Rica Continental")
                else:
                    query = query.eq("id", request.region_id)
                res = query.limit(1).execute()
                if res.data:
                    row = res.data[0]
                    return (
                        GeoJSONPolygon.model_validate(row["geom"]),
                        str(row["id"]),
                        row["name"],
                        row["boundary_source"],
                        row["boundary_version"],
                    )
            except Exception:
                pass

        for r in DEFAULT_REGIONS:
            if r.id == request.region_id or (r.id == "costa-rica-continental" and request.region_id in (r.id, "costa-rica")):
                return (
                    r.geom,
                    r.id,
                    r.name,
                    r.boundary_source,
                    r.boundary_version,
                )
        raise HTTPException(
            status_code=404,
            detail=f"La región con identificador '{request.region_id}' no existe en el catálogo.",
        )
    elif request.region:
        return (
            request.region,
            "custom-polygon",
            "Polígono personalizado",
            "Usuario / Solicitud directa",
            "1.0",
        )
    raise HTTPException(
        status_code=400,
        detail="Debe proporcionar 'region_id' o 'region' con una geometría válida.",
    )


def validate_exploration_request(request: ExplorationRequest) -> None:
    start = request.start_date
    end = request.end_date

    if start is None or end is None:
        raise HTTPException(
            status_code=400,
            detail="Las fechas 'start_date' y 'end_date' son obligatorias.",
        )

    if start.day != 1:
        raise HTTPException(
            status_code=400,
            detail=f"La fecha de inicio {start} debe ser el primer día de un mes (ej. YYYY-MM-01).",
        )

    last_day_of_end_month = calendar.monthrange(end.year, end.month)[1]
    if end.day != last_day_of_end_month:
        raise HTTPException(
            status_code=400,
            detail=(
                f"La fecha final {end} debe ser el último día del mes respectivo "
                f"({end.year}-{end.month:02d}-{last_day_of_end_month})."
            ),
        )

    if start < MIN_SUPPORTED_DATE or end > MAX_SUPPORTED_DATE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"El rango solicitado [{start}, {end}] está fuera del intervalo disponible "
                f"para IMERG V07 [{MIN_SUPPORTED_DATE}, {MAX_SUPPORTED_DATE}]."
            ),
        )


def _fetch_from_supabase(
    supabase: Any,
    request: ExplorationRequest,
    start: date,
    end: date,
    region_uuid: str | None = None,
) -> pd.DataFrame | None:
    # Solo consultar en Supabase si se trata de una región registrada con UUID válido
    if not region_uuid or len(region_uuid) != 36:
        return None

    try:
        start_str = start.isoformat()
        end_str = end.isoformat()

        query = (
            supabase.table("ingestion_runs")
            .select("id")
            .eq("region_id", region_uuid)
            .eq("variable_id", request.variable_id)
            .lte("requested_start", start_str)
            .gte("requested_end", end_str)
        )
        runs_query = query.limit(1).execute()
        if not runs_query.data:
            return None

        run_id = runs_query.data[0]["id"]
        data_query = (
            supabase.table("processed_data")
            .select("observed_month, precipitation_mm, coverage_fraction, quality_flag")
            .eq("ingestion_run_id", run_id)
            .gte("observed_month", start_str)
            .lte("observed_month", end_str)
            .order("observed_month")
            .execute()
        )
        rows = data_query.data
        if not rows:
            return None

        expected_months = pd.date_range(start=start, end=end, freq="MS")
        if len(rows) != len(expected_months):
            return None

        records = {}
        for row in rows:
            m = pd.Timestamp(row["observed_month"])
            val = (
                float(row["precipitation_mm"])
                if row["precipitation_mm"] is not None
                else float("nan")
            )
            cov = float(row["coverage_fraction"])
            qual = str(row["quality_flag"])
            records[m] = (val, cov, qual)

        df = pd.DataFrame.from_dict(
            records,
            orient="index",
            columns=("precipitation_mm", "coverage_fraction", "quality_flag"),
        ).reindex(expected_months)
        df.index.name = "month"
        return df
    except Exception:
        return None


def run_exploration(
    request: ExplorationRequest,
    *,
    connector: GPMIMERGConnector | None = None,
    supabase_client: Any | None = None,
) -> ExplorationResponse:
    validate_exploration_request(request)

    start = request.start_date  # type: ignore[assignment]
    end = request.end_date      # type: ignore[assignment]

    geom, region_id, region_name, b_source, b_version = resolve_region(
        request, supabase_client
    )

    monthly_frame: pd.DataFrame | None = None

    # 1. Intentar consultar datos en caché local (disco/memoria)
    monthly_frame = load_from_cache(
        request.variable_id, region_id, geom, start, end
    )

    # 2. Si no está en caché local, intentar consultar en Supabase
    if monthly_frame is None and supabase_client is not None:
        monthly_frame = _fetch_from_supabase(
            supabase_client, request, start, end, region_id
        )

    # 3. Si no están en caché, obtener mediante el conector IMERG en vivo
    if monthly_frame is None:
        if connector is None:
            connector = GPMIMERGConnector()

        try:
            result = connector.fetch_monthly_precipitation(
                geom,
                start,
                end,
            )
            monthly_frame = prepare_monthly_precipitation(result, start, end)
            save_to_cache(
                request.variable_id, region_id, geom, start, end, monthly_frame
            )
            if supabase_client is not None:
                save_to_supabase(
                    supabase_client, request, geom, result, monthly_frame, region_id
                )
        except (DataUnavailableError, DataIntegrityError) as e:
            raise HTTPException(
                status_code=502,
                detail=f"Error en datos satelitales NASA: {e}",
            )
        except GPMIMERGError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Error del conector NASA IMERG: {e}",
            )
        except PrecipitationProcessingError as e:
            raise HTTPException(
                status_code=422,
                detail=f"Error procesando serie temporal: {e}",
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Fallo inesperado durante la consulta de datos: {e}",
            )

    # 3. Procesamiento analítico: Línea base y anomalías
    try:
        frame_with_anomalies = calculate_climatology_and_anomalies(monthly_frame)
    except TrendAnalysisError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error calculando anomalías climáticas: {e}",
        )

    # 4. Agregación anual
    try:
        annual_frame = aggregate_annual_precipitation(frame_with_anomalies)
    except PrecipitationProcessingError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error agregando totales anuales: {e}",
        )

    # 5. Análisis estadístico de tendencias
    try:
        trend_analysis = analyze_annual_trend(annual_frame)
    except TrendAnalysisError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error evaluando tendencias: {e}",
        )

    # 6. Serialización a modelos Pydantic
    timeseries = [
        TimeSeriesPoint(
            date=month_ts.date(),
            value=(
                None
                if math.isnan(row["precipitation_mm"])
                else round(float(row["precipitation_mm"]), 2)
            ),
            coverage_fraction=round(float(row["coverage_fraction"]), 4),
            quality_flag=row["quality_flag"],
            anomaly_mm=(
                None
                if math.isnan(row["anomaly_mm"])
                else round(float(row["anomaly_mm"]), 2)
            ),
        )
        for month_ts, row in frame_with_anomalies.iterrows()
    ]

    annual_totals = [
        AnnualPrecipitation(
            year=int(year),
            annual_precipitation_mm=round(float(row["annual_precipitation_mm"]), 2),
            months_reported=12,
        )
        for year, row in annual_frame.iterrows()
    ]

    selection = EffectiveSelection(
        region_id=region_id,
        region_name=region_name,
        boundary_source=b_source,
        boundary_version=b_version,
        requested_period=DateRange(start=start, end=end),
        effective_period=DateRange(start=start, end=end),
    )

    metadata = ExplorationMetadata(
        variable_name="Precipitación mensual estimada",
        source="NASA GES DISC / Giovanni",
        dataset="GPM_3IMERGM.07",
        unit="mm/month",
        spatial_resolution="0.1° (~10 km); promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)",
        temporal_resolution="monthly",
        selection=selection,
        limitations=[
            "Estimación satelital combinada con calibración mensual de pluviómetros, no una medición puntual de estación meteorológica.",
            "El polígono corresponde a una delimitación territorial para el MVP de Iyök.",
            "La resolución de 0.1° promedia variaciones locales en microclimas y topografías montañosas complejas.",
        ],
        warnings=[
            "IMERG no sustituye mediciones de estaciones en superficie.",
            "Posibles sesgos en zonas de costa y alta montaña deben verificarse según el área elegida.",
        ],
    )

    interpretation = generate_interpretation(
        metadata=metadata,
        trend_analysis=trend_analysis,
        frame_with_anomalies=frame_with_anomalies,
        annual_totals=annual_totals,
    )

    return ExplorationResponse(
        status="success",
        metadata=metadata,
        trend_analysis=trend_analysis,
        interpretation=interpretation,
        timeseries=timeseries,
        annual_totals=annual_totals,
    )
