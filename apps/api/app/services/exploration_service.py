from __future__ import annotations

import calendar
import hashlib
import json
import logging
import math
import os
from datetime import UTC, date, datetime, timezone
from typing import Any, Callable

import pandas as pd
from fastapi import HTTPException

# Codex (Manuel): la validación espacial se mantiene; la caché se gobierna internamente.
from app.core.cache import load_from_cache, save_to_cache, save_to_supabase
from app.core.security import is_write_authorized, validate_polygon_complexity_and_area
from app.core.supabase_cache import load_supabase_series, save_supabase_series
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
    TimeSeriesPoint,
    TrendAnalysis,
)
from app.models.geojson import GeoJSONMultiPolygon, GeoJSONPolygon, are_geometries_equal
from app.models.regions import Region
from app.models.variables import AvailableInterval, Variable
from app.services.gpm_imerg import (
    DataIntegrityError,
    DataUnavailableError,
    EarthdataAuthenticationRequired,
    GPMIMERGConnector,
    GPMIMERGError,
    GPMIMERGResult,
)
from app.services.interpretation_service import generate_interpretation
from app.services.preprocessed_series import load_preprocessed_series
from app.services.snit_series import GEOMETRY_SHA, REGION_ID as SNIT_REGION_ID, load_snit
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

logger = logging.getLogger(__name__)

MIN_SUPPORTED_DATE = date(1998, 1, 1)
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

DEFAULT_PANAMA_CANAL_GEOM = GeoJSONPolygon(
    type="Polygon",
    coordinates=[
        [
            [-80.00, 8.80],
            [-79.50, 8.80],
            [-79.50, 9.30],
            [-80.00, 9.30],
            [-80.00, 8.80],
        ]
    ],
)

DEFAULT_CHIQUIMULA_GEOM = GeoJSONPolygon(
    type="Polygon",
    coordinates=[
        [
            [-89.65, 14.65],
            [-89.30, 14.65],
            [-89.30, 15.00],
            [-89.65, 15.00],
            [-89.65, 14.65],
        ]
    ],
)

DEFAULT_REGIONS = [
    Region(
        id="costa-rica-continental",
        name="Costa Rica Continental",
        # Codex (Manuel): el polígono simplificado carece de procedencia cartográfica verificable.
        description="Geometría aproximada de Costa Rica continental; no es una frontera oficial validada.",
        boundary_source="Geometría aproximada no verificada",
        boundary_version="provisional",
        geom=DEFAULT_COSTA_RICA_GEOM,
    ),
    Region(
        id="cuenca-canal-panama",
        name="Cuenca del Canal de Panamá",
        description="Subcuenca hidrográfica del Canal de Panamá (Alajuela / Gatún / Miraflores) en la República de Panamá.",
        boundary_source="Autoridad del Canal de Panamá (ACP) / STRI",
        boundary_version="2024",
        geom=DEFAULT_PANAMA_CANAL_GEOM,
    ),
    Region(
        id="corredor-seco-chiquimula",
        name="Corredor Seco - Chiquimula",
        description="Zona semiárida oriental de Guatemala en el Corredor Seco Centroamericano.",
        boundary_source="MAGA Guatemala / FAO",
        boundary_version="2024",
        geom=DEFAULT_CHIQUIMULA_GEOM,
    ),
]

DEFAULT_VARIABLES = [
    Variable(
        id="precipitation",
        name="Precipitación mensual estimada",
        source="NASA GPM IMERG Final Run (GPM_3IMERGM V07), GES DISC",
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
    regions_list.append(CatalogRegion(
        id=SNIT_REGION_ID, name="Costa Rica continental — IGN/SNIT",
        description="Componente terrestre principal IGN/SNIT; componentes separados excluidos del MVP.",
        boundary_source="IGN / Registro Nacional / SNIT", boundary_version="snit-continental-2026-11-15-v1",
        geom=None, geometry_sha256=GEOMETRY_SHA,
    ))

    has_earthdata_token = bool(os.environ.get("EARTHDATA_TOKEN", "").strip())

    variables_list = [
        CatalogVariable(
            id="precipitation",
            name="Precipitación mensual estimada",
            source="NASA GES DISC; mecanismo de acceso según la consulta (CMR / Harmony / Giovanni)",
            dataset="GPM_3IMERGM.07",
            unit="mm/month",
            spatial_resolution="0.1° (~10 km); promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)",
            temporal_resolution="monthly",
            available_interval=AvailableInterval(
                start=MIN_SUPPORTED_DATE,
                end=MAX_SUPPORTED_DATE,
            ),
            declared_interval=AvailableInterval(
                start=MIN_SUPPORTED_DATE,
                end=MAX_SUPPORTED_DATE,
            ),
            verified_interval=AvailableInterval(
                start=MIN_SUPPORTED_DATE,
                end=MAX_SUPPORTED_DATE,
            ),
            known_gaps=[],
            doi_or_link="https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07",
            source_status="verified",
            restrictions=[
                "Requiere fechas alineadas a mes completo (primer día a último día de mes).",
                "Estimación satelital combinada con pluviómetros; no sustituye estaciones puntuales.",
            ],
        )
    ]

    # Costa Rica cuenta con cobertura verificada en CMR/Harmony desde 1998 (324 meses) y archivo preprocesado 2001-2024
    cr_combination = CatalogCombination(
        region_id="costa-rica-continental",
        variable_id="precipitation",
        available_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
        declared_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
        verified_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
        known_gaps=[],
        source_status="verified",
        temporal_resolution="monthly",
        is_ready_for_exploration=True,
        notes="Serie continua histórica 1998-2024 verificada en catálogo NASA (324 meses); período 2001-2024 disponible de inmediato en archivo preprocesado y 1998-2000 bajo demanda.",
    )

    panama_status = "on_demand" if has_earthdata_token else "source_unavailable"
    panama_ready = has_earthdata_token
    panama_combination = CatalogCombination(
        region_id="cuenca-canal-panama",
        variable_id="precipitation",
        available_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
        declared_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
        verified_interval=(
            AvailableInterval(start=MIN_SUPPORTED_DATE, end=MAX_SUPPORTED_DATE)
            if has_earthdata_token
            else None
        ),
        known_gaps=[],
        source_status=panama_status,
        temporal_resolution="monthly",
        is_ready_for_exploration=panama_ready,
        notes=(
            "Extracción satelital GPM IMERG V07 disponible bajo demanda mediante NASA Harmony."
            if has_earthdata_token
            else "Fuente en vivo no disponible de inmediato: requiere configurar EARTHDATA_TOKEN en el servidor para extracción remota."
        ),
    )

    chiquimula_status = "on_demand" if has_earthdata_token else "source_unavailable"
    chiquimula_ready = has_earthdata_token
    chiquimula_combination = CatalogCombination(
        region_id="corredor-seco-chiquimula",
        variable_id="precipitation",
        available_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
        declared_interval=AvailableInterval(
            start=MIN_SUPPORTED_DATE,
            end=MAX_SUPPORTED_DATE,
        ),
        verified_interval=(
            AvailableInterval(start=MIN_SUPPORTED_DATE, end=MAX_SUPPORTED_DATE)
            if has_earthdata_token
            else None
        ),
        known_gaps=[],
        source_status=chiquimula_status,
        temporal_resolution="monthly",
        is_ready_for_exploration=chiquimula_ready,
        notes=(
            "Extracción satelital GPM IMERG V07 disponible bajo demanda mediante NASA Harmony."
            if has_earthdata_token
            else "Fuente en vivo no disponible de inmediato: requiere configurar EARTHDATA_TOKEN en el servidor para extracción remota."
        ),
    )

    combinations = [cr_combination, panama_combination, chiquimula_combination]
    snit_ready = load_snit() is not None
    combinations.append(CatalogCombination(
        region_id=SNIT_REGION_ID, variable_id="precipitation",
        available_interval=AvailableInterval(start=MIN_SUPPORTED_DATE, end=MAX_SUPPORTED_DATE),
        declared_interval=AvailableInterval(start=MIN_SUPPORTED_DATE, end=MAX_SUPPORTED_DATE),
        verified_interval=AvailableInterval(start=MIN_SUPPORTED_DATE, end=MAX_SUPPORTED_DATE) if snit_ready else None,
        source_status="verified" if snit_ready else "unavailable",
        temporal_resolution="monthly", is_ready_for_exploration=snit_ready,
        notes="Serie local verificada para la geometría SNIT indicada." if snit_ready else "La serie o su geometría no están disponibles o no pasaron la comprobación de integridad.",
    ))

    return CatalogResponse(
        status="success",
        regions=regions_list,
        variables=variables_list,
        combinations=combinations,
    )


def resolve_region(
    request: ExplorationRequest,
    supabase_client: Any | None = None,
) -> tuple[GeoJSONPolygon | GeoJSONMultiPolygon, str, str, str, str, str | None]:
    """Resuelve la geometría y metadatos de la región a partir de region_id o polígono directo.

    Retorna: (geom, public_region_id, region_name, boundary_source, boundary_version, internal_uuid)
    - public_region_id: Identificador público estable que coincide con el catálogo y la solicitud del cliente.
    - internal_uuid: UUID interno de Supabase (si aplica) para trazabilidad e integridad relacional.
    """
    if request.region_id:
        resolved_geom: GeoJSONPolygon | None = None
        public_region_id: str = request.region_id
        region_name: str | None = None
        boundary_source: str | None = None
        boundary_version: str | None = None
        internal_uuid: str | None = None

        # Codex (Manuel): las regiones publicadas en catálogo usan esa misma geometría en la consulta.
        known_region = any(r.id == request.region_id for r in DEFAULT_REGIONS) or request.region_id in (
            "costa-rica", "panama-canal", "panama", "corredor-seco"
        )
        if supabase_client is not None and not known_region:
            try:
                query = supabase_client.table("regions").select(
                    "id, name, boundary_source, boundary_version, geom"
                )
                if len(request.region_id) == 36 and "-" in request.region_id:
                    query = query.eq("id", request.region_id)
                elif request.region_id in ("costa-rica-continental", "costa-rica"):
                    query = query.eq("name", "Costa Rica Continental")
                elif request.region_id in ("cuenca-canal-panama", "panama-canal", "panama"):
                    query = query.eq("name", "Cuenca del Canal de Panamá")
                elif request.region_id in ("corredor-seco-chiquimula", "corredor-seco"):
                    query = query.eq("name", "Corredor Seco - Chiquimula")
                else:
                    query = query.eq("name", request.region_id)
                res = query.limit(1).execute()
                if res.data:
                    row = res.data[0]
                    resolved_geom = GeoJSONPolygon.model_validate(row["geom"])
                    internal_uuid = str(row["id"])
                    region_name = row["name"]
                    boundary_source = row["boundary_source"]
                    boundary_version = row["boundary_version"]
            except Exception as e:  # noqa: BLE001 - boundary fallback
                logger.debug("Error buscando región en Supabase: %s", e)

        if resolved_geom is None:
            for r in DEFAULT_REGIONS:
                if (
                    r.id == request.region_id
                    or (r.id == "costa-rica-continental" and request.region_id in (r.id, "costa-rica"))
                    or (r.id == "cuenca-canal-panama" and request.region_id in (r.id, "panama-canal", "panama"))
                    or (r.id == "corredor-seco-chiquimula" and request.region_id in (r.id, "corredor-seco"))
                ):
                    resolved_geom = r.geom
                    region_name = r.name
                    boundary_source = r.boundary_source
                    boundary_version = r.boundary_version
                    internal_uuid = None
                    break

        if resolved_geom is None:
            raise HTTPException(
                status_code=404,
                detail=f"La región con identificador '{request.region_id}' no existe en el catálogo.",
            )

        # Criterio 3: Si se envía geometría y region_id, verificar compatibilidad estricta
        if request.region is not None:
            if not are_geometries_equal(request.region, resolved_geom):
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Incompatibilidad geométrica: La geometría provista en 'region' no coincide "
                        f"con la geometría oficial declarada para la región '{request.region_id}'."
                    ),
                )
            resolved_geom = request.region

        return (
            resolved_geom,
            public_region_id,
            region_name or "Región Desconocida",
            boundary_source or "Fuente no especificada",
            boundary_version or "1.0",
            internal_uuid,
        )

    elif request.region:
        geom_hash = hashlib.sha256(
            json.dumps(request.region.coordinates, sort_keys=True).encode("utf-8")
        ).hexdigest()[:12]
        custom_name = f"Polígono Personalizado ({geom_hash})"
        return (
            request.region,
            "custom-polygon",
            custom_name,
            "Usuario / Solicitud directa",
            "1.0",
            None,
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

    # Validar complejidad y extensión del polígono si se proporciona geometría personalizada
    if request.region is not None:
        validate_polygon_complexity_and_area(request.region.coordinates, multipolygon=request.region.type == "MultiPolygon")

    # Incompatibilidad geométrica temprana para regiones de catálogo predeterminado
    if request.region_id and request.region is not None:
        for r in DEFAULT_REGIONS:
            if (
                r.id == request.region_id
                or (r.id == "costa-rica-continental" and request.region_id in (r.id, "costa-rica"))
                or (r.id == "cuenca-canal-panama" and request.region_id in (r.id, "panama-canal", "panama"))
                or (r.id == "corredor-seco-chiquimula" and request.region_id in (r.id, "corredor-seco"))
            ):
                if not are_geometries_equal(request.region, r.geom):
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Incompatibilidad geométrica: La geometría provista en 'region' no coincide "
                            f"con la geometría oficial declarada para la región '{request.region_id}'."
                        ),
                    )
                break


def _fetch_from_supabase(
    supabase: Any,
    request: ExplorationRequest,
    start: date,
    end: date,
    region_identifier: str | None = None,
    geom: GeoJSONPolygon | None = None,
) -> pd.DataFrame | None:
    if not supabase:
        return None

    # Criterio 1: Polígono personalizado nunca se consulta en Supabase sin identidad verificada de catálogo
    if region_identifier == "custom-polygon" or request.region is not None:
        return None

    try:
        region_uuid: str | None = None
        if region_identifier and len(region_identifier) == 36 and "-" in region_identifier:
            res = (
                supabase.table("regions")
                .select("id, name, geom")
                .eq("id", region_identifier)
                .limit(1)
                .execute()
            )
            if res.data:
                region_uuid = str(res.data[0]["id"])
        elif region_identifier:
            name_candidates = []
            if region_identifier in ("costa-rica-continental", "costa-rica"):
                name_candidates = ["Costa Rica Continental"]
            elif region_identifier in ("cuenca-canal-panama", "panama-canal", "panama"):
                name_candidates = ["Cuenca del Canal de Panamá"]
            elif region_identifier in ("corredor-seco-chiquimula", "corredor-seco"):
                name_candidates = ["Corredor Seco - Chiquimula"]

            for candidate in name_candidates:
                res = (
                    supabase.table("regions")
                    .select("id, name, geom")
                    .eq("name", candidate)
                    .limit(1)
                    .execute()
                )
                if res.data:
                    region_uuid = str(res.data[0]["id"])
                    break

        if not region_uuid:
            return None

        start_str = start.isoformat()
        end_str = end.isoformat()

        # Selección determinista: buscar runs que cubran el intervalo ordenados por created_at desc
        query = (
            supabase.table("ingestion_runs")
            .select(
                "id, region_geometry_snapshot, dataset_id, dataset_version, source_units, "
                "output_units, unit_conversion, spatial_resolution_degrees, weighting_method, "
                "source_granule_ids, region_source_snapshot, created_at"
            )
            .eq("region_id", region_uuid)
            .eq("variable_id", request.variable_id)
            .lte("requested_start", start_str)
            .gte("requested_end", end_str)
            .order("created_at", desc=True)
        )
        runs_query = query.execute()
        if not runs_query.data:
            return None

        expected_months = pd.date_range(start=start, end=end, freq="MS")

        # Evaluar candidatos de forma determinista para descartar cualquier ingesta incompleta o incompatible
        for run_candidate in runs_query.data:
            run_id = run_candidate["id"]
            snapshot = run_candidate.get("region_geometry_snapshot")
            if snapshot is not None and geom is not None and not are_geometries_equal(snapshot, geom):
                logger.warning(
                    "Ingestion run %s tiene una geometría de ingesta incompatible con la consultada; omitiendo candidato.",
                    run_id,
                )
                continue

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
            if not rows or len(rows) != len(expected_months):
                logger.warning(
                    "Ingestion run %s incompleto (%d meses de %d esperados); omitiendo.",
                    run_id,
                    len(rows) if rows else 0,
                    len(expected_months),
                )
                continue

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

            # Preservar procedencia explícita comprobada
            snapshot_src = str(run_candidate.get("region_source_snapshot") or "").lower()
            if "giovanni" in snapshot_src or "costa-rica" in str(region_identifier or ""):
                eff_origin = "NASA Giovanni"
                source_label = "NASA GES DISC / Giovanni"
            else:
                eff_origin = run_candidate.get("region_source_snapshot") or "NASA Harmony"
                source_label = "NASA GES DISC / Harmony"

            provenance = {
                "effective_origin": eff_origin,
                "source": source_label,
                "dataset": run_candidate.get("dataset_id") or "GPM_3IMERGM.07",
                "product_version": run_candidate.get("dataset_version") or "07",
                "processing_version": "1.0",
                "doi_or_link": "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07",
                "source_units": run_candidate.get("source_units") or "mm/hr",
                "output_units": run_candidate.get("output_units") or "mm/month",
                "unit_conversion": (
                    run_candidate.get("unit_conversion")
                    or "Multiplicación por horas del mes calendario según año bisiesto"
                ),
                "spatial_resolution": (
                    f"{run_candidate.get('spatial_resolution_degrees', 0.1)}°; "
                    "promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
                ),
                "weighting_method": (
                    run_candidate.get("weighting_method")
                    or "Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
                ),
                "source_granule_ids": run_candidate.get("source_granule_ids") or [],
                "data_accessed_at": run_candidate.get("created_at"),
                "quality_method": "Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)",
                "region_geometry_snapshot": snapshot,
            }
            df.attrs["provenance"] = provenance

            logger.info(
                "Caché Supabase HIT para region_uuid %s en rango [%s, %s] (run_id: %s)",
                region_uuid,
                start_str,
                end_str,
                run_id,
            )
            return df

        return None
    except Exception as e:  # noqa: BLE001 - boundary fallback
        logger.warning("Error consultando caché en Supabase: %s", e)
        return None


def run_exploration(
    request: ExplorationRequest,
    *,
    connector: GPMIMERGConnector | None = None,
    supabase_client: Any | None = None,
    request_headers: dict[str, str] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> ExplorationResponse:
    validate_exploration_request(request)

    start = request.start_date  # type: ignore[assignment]
    end = request.end_date      # type: ignore[assignment]

    is_snit = request.region_id == SNIT_REGION_ID
    if is_snit:
        if request.region is not None:
            raise HTTPException(status_code=422, detail="La región SNIT usa una geometría interna identificada por huella; no admite una geometría adicional.")
        geom, region_id, region_name, b_source, b_version = None, SNIT_REGION_ID, "Costa Rica continental — IGN/SNIT", "IGN / Registro Nacional / SNIT", "snit-continental-2026-11-15-v1"
    else:
        geom, region_id, region_name, b_source, b_version, _internal_uuid = resolve_region(request, supabase_client)

    monthly_frame: pd.DataFrame | None = None
    nasa_result: GPMIMERGResult | None = None
    provenance_info: dict[str, Any] | None = None
    preprocessed = False
    cached = None

    direct_nasa = os.environ.get("IYOK_DATA_SOURCE", "nasa").strip().lower() == "nasa"
    cache_status = "disabled" if direct_nasa else "unavailable" if supabase_client is None else "miss"
    if is_snit:
        cached = load_snit(start, end)
        if cached is None:
            raise HTTPException(status_code=503, detail="La serie SNIT no está disponible o no pasó la verificación de integridad.", headers={"X-Iyok-Error-Code": "SNIT_SERIES_UNAVAILABLE"})
        monthly_frame, cache_status, preprocessed = cached.frame, "preprocessed", True
        provenance_info = {
            "effective_origin": "NASA Harmony", "source": cached.metadata["source"],
            "dataset": cached.metadata["dataset"], "product_version": "07", "processing_version": "snit-v1",
            "doi_or_link": "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07",
            "source_units": cached.metadata["source_units"], "unit_conversion": cached.metadata["unit_conversion"],
            "weighting_method": cached.metadata["weighting_method"], "source_granule_ids": cached.metadata["source_granule_ids"],
            "quality_method": "Cobertura espacial calculada sobre la geometría SNIT",
        }
    if not is_snit and not direct_nasa and request.region is None:
        preprocessed_cached = load_preprocessed_series(region_id, geom, start, end)
        if preprocessed_cached:
            monthly_frame = preprocessed_cached.frame
            cache_status = "preprocessed"
            preprocessed = True
            cached = preprocessed_cached
            provenance_info = {
                "effective_origin": "NASA Harmony",
                "source": "Archivo local preprocesado desde NASA CMR y Harmony",
                "dataset": preprocessed_cached.metadata.get("dataset", "GPM_3IMERGM.07"),
                "product_version": "07",
                "processing_version": "1.0",
                "doi_or_link": "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07",
                "source_units": preprocessed_cached.metadata.get("source_units", "mm/hr"),
                "output_units": preprocessed_cached.metadata.get("output_units", "mm/month"),
                "unit_conversion": (
                    preprocessed_cached.metadata.get("unit_conversion")
                    or "Multiplicación por horas del mes calendario según año bisiesto"
                ),
                "spatial_resolution": "0.1°; promedio espacial ponderado por área equivalente (EPSG:6933)",
                "weighting_method": (
                    preprocessed_cached.metadata.get("weighting_method")
                    or "Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
                ),
                "source_granule_ids": preprocessed_cached.metadata.get("source_granule_ids", []),
                "data_accessed_at": (
                    preprocessed_cached.metadata.get("created_at")
                    or datetime.now(timezone.utc).isoformat()
                ),
                "quality_method": "Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)",
                "region_geometry_snapshot": geom.model_dump(),
            }

    # 2. Si no hay serie preprocesada y se pasó supabase_client, consultar Supabase
    if monthly_frame is None and not direct_nasa and supabase_client is not None and request.region is None:
        supabase_cached = load_supabase_series(supabase_client, region_id, geom, start, end)
        if supabase_cached:
            monthly_frame = supabase_cached.frame
            cache_status = "hit"
            cached = supabase_cached
            provenance_info = {
                "effective_origin": "NASA Harmony",
                "source": "Supabase: serie previamente procesada desde NASA CMR y Harmony",
                "dataset": supabase_cached.metadata.get("dataset_id", "GPM_3IMERGM.07"),
                "product_version": supabase_cached.metadata.get("dataset_version", "07"),
                "processing_version": "1.0",
                "doi_or_link": "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07",
                "source_units": supabase_cached.metadata.get("source_units", "mm/hr"),
                "output_units": supabase_cached.metadata.get("output_units", "mm/month"),
                "unit_conversion": (
                    supabase_cached.metadata.get("unit_conversion")
                    or "Multiplicación por horas del mes calendario según año bisiesto"
                ),
                "spatial_resolution": "0.1°; promedio espacial ponderado por área equivalente (EPSG:6933)",
                "weighting_method": (
                    supabase_cached.metadata.get("weighting_method")
                    or "Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
                ),
                "source_granule_ids": supabase_cached.metadata.get("source_granule_ids", []),
                "data_accessed_at": (
                    supabase_cached.metadata.get("created_at")
                    or datetime.now(timezone.utc).isoformat()
                ),
                "quality_method": "Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)",
                "region_geometry_snapshot": geom.model_dump(),
            }

    # 3. Intentar caché local con procedencia (cuando no se delega a Supabase para regiones de catálogo)
    if monthly_frame is None and not direct_nasa and (supabase_client is None or request.region is not None):
        cached_result = load_from_cache(
            request.variable_id, region_id, geom, start, end, with_provenance=True
        )
        if cached_result is not None:
            monthly_frame, provenance_info = cached_result
            cache_status = "hit"

    # 4. Si no están en caché, obtener mediante el conector IMERG en vivo
    if monthly_frame is None:
        if connector is None:
            connector = GPMIMERGConnector()

        try:
            nasa_result = connector.fetch_monthly_precipitation(
                geom,
                start,
                end,
                progress_callback=progress_callback,
                cancel_check=cancel_check,
            )
            monthly_frame = prepare_monthly_precipitation(nasa_result, start, end)
            provenance_info = {
                "effective_origin": "NASA Harmony",
                "source": "NASA GES DISC mediante CMR y Harmony",
                "dataset": nasa_result.dataset,
                "product_version": nasa_result.version,
                "processing_version": "1.0",
                "doi_or_link": "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07",
                "source_units": nasa_result.source_units,
                "output_units": nasa_result.output_units,
                "unit_conversion": nasa_result.unit_conversion,
                "spatial_resolution": (
                    f"{nasa_result.spatial_resolution_degrees}° (~10 km); "
                    "promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
                ),
                "weighting_method": nasa_result.weighting_method,
                "source_granule_ids": list(nasa_result.granule_ids),
                "data_accessed_at": datetime.now(timezone.utc).isoformat(),
                "quality_method": "Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)",
                "region_geometry_snapshot": geom.model_dump(),
            }
            monthly_frame.attrs["provenance"] = provenance_info
            if supabase_client is None or request.region is not None:
                save_to_cache(
                    request.variable_id,
                    region_id,
                    geom,
                    start,
                    end,
                    monthly_frame,
                    provenance=provenance_info,
                )
            # Codex (Manuel): la caché pública es escritura interna del servidor, sin clave en el navegador.
            if (
                not direct_nasa
                and supabase_client is not None
                and request.region is None
                and os.environ.get("IYOK_ALLOW_WRITE", "true").strip().lower() != "false"
            ):
                if save_supabase_series(
                    supabase_client, region_id, geom, start, end, nasa_result, monthly_frame
                ):
                    cache_status = "stored"
                elif is_write_authorized(request_headers):
                    save_to_supabase(
                        supabase_client,
                        request,
                        geom,
                        nasa_result,
                        monthly_frame,
                        _internal_uuid or region_id,
                    )
                    cache_status = "stored"
        except EarthdataAuthenticationRequired:
            raise HTTPException(
                status_code=503,
                detail="La consulta NASA requiere configurar Earthdata en el servidor.",
                headers={"X-Iyok-Error-Code": "NASA_AUTH_REQUIRED"},
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
        except Exception:  # noqa: BLE001 - boundary fallback
            raise HTTPException(
                status_code=502,
                detail="No se pudo completar la consulta de datos NASA. Revise el acceso del servidor.",
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

    # La corrección serial actual no controla el error en escenarios simulados.
    # Conservar la serie, pero no publicar inferencias hasta revisar el método.
    if trend_analysis.status == "conclusive":
        trend_analysis = TrendAnalysis(
            status="inconclusive",
            method=trend_analysis.method,
            slope=None, slope_unit=None, p_value=None, is_significant=None, confidence_level=None,
            summary="La tendencia estadística no puede interpretarse con el método actual.",
            methodological_note="La corrección por dependencia temporal mostró exceso de falsos positivos en simulaciones; requiere revisión antes de informar significancia.",
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
            coverage_fraction=round(float(row["coverage_fraction"]), 6),
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
        geometry_sha256=GEOMETRY_SHA if is_snit else None,
        requested_period=DateRange(start=start, end=end),
        effective_period=DateRange(start=start, end=end),
    )

    if provenance_info:
        eff_origin = provenance_info.get("effective_origin", "NASA Harmony")
        source_label = provenance_info.get("source", "NASA GES DISC mediante CMR y Harmony")
        dataset_label = provenance_info.get("dataset", "GPM_3IMERGM.07")
        product_ver = provenance_info.get("product_version", "07")
        proc_ver = provenance_info.get("processing_version", "1.0")
        doi_link = provenance_info.get(
            "doi_or_link", "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07"
        )
        src_units = provenance_info.get("source_units", "mm/hr")
        u_conv = provenance_info.get(
            "unit_conversion",
            "Multiplicación por horas del mes calendario según año bisiesto",
        )
        w_method = provenance_info.get(
            "weighting_method",
            "Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)",
        )
        spat_res = provenance_info.get(
            "spatial_resolution",
            "0.1° (~10 km); promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)",
        )
        granules = provenance_info.get("source_granule_ids")
        q_method = provenance_info.get(
            "quality_method",
            "Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)",
        )
        acc_at = provenance_info.get("data_accessed_at")
        if isinstance(acc_at, str):
            try:
                acc_at_dt = datetime.fromisoformat(acc_at)
            except Exception:
                acc_at_dt = datetime.now(timezone.utc)
        elif isinstance(acc_at, datetime):
            acc_at_dt = acc_at
        else:
            acc_at_dt = None if is_snit else datetime.now(timezone.utc)
    elif nasa_result:
        eff_origin = "NASA Harmony"
        source_label = "NASA GES DISC mediante CMR y Harmony"
        dataset_label = nasa_result.dataset
        product_ver = nasa_result.version
        proc_ver = "1.0"
        doi_link = "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07"
        src_units = nasa_result.source_units
        u_conv = nasa_result.unit_conversion
        w_method = nasa_result.weighting_method
        spat_res = (
            f"{nasa_result.spatial_resolution_degrees}° (~10 km); "
            "promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
        )
        granules = list(nasa_result.granule_ids)
        q_method = "Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)"
        acc_at_dt = datetime.now(timezone.utc)
    else:
        eff_origin = "NASA Harmony"
        source_label = "NASA GES DISC mediante CMR y Harmony"
        dataset_label = "GPM_3IMERGM.07"
        product_ver = "07"
        proc_ver = "1.0"
        doi_link = "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07"
        src_units = "mm/hr"
        u_conv = "Multiplicación por horas del mes calendario según año bisiesto"
        w_method = "Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
        spat_res = "0.1° (~10 km); promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"
        granules = None
        q_method = "Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)"
        acc_at_dt = datetime.now(timezone.utc)

    metadata = ExplorationMetadata(
        variable_name="Precipitación mensual estimada",
        source=source_label,
        dataset=dataset_label,
        unit="mm/month",
        spatial_resolution=spat_res,
        temporal_resolution="monthly",
        selection=selection,
        effective_origin=eff_origin,
        product_version=product_ver,
        processing_version=proc_ver,
        doi_or_link=doi_link,
        source_units=src_units,
        unit_conversion=u_conv,
        weighting_method=w_method,
        source_granule_ids=granules,
        data_accessed_at=acc_at_dt,
        quality_method=q_method,
        geometry_snapshot=geom.model_dump() if geom is not None else None,
        cache_status=cache_status,
        limitations=[
            "Estimación satelital combinada con calibración mensual de pluviómetros, no una medición puntual de estación meteorológica.",
            # Codex (Manuel): describir la geometría efectiva sin atribuirle una fuente sin verificar.
            f"Geometría de análisis: {b_source}, versión {b_version}; confirme su representatividad territorial.",
            "La resolución de 0.1° promedia variaciones locales en microclimas y topografías montañosas complejas.",
        ],
        warnings=[
            "IMERG no sustituye mediciones de estaciones en superficie.",
            "Posibles sesgos en zonas de costa y alta montaña deben verificarse según el área elegida.",
            *(["Serie SNIT preprocesada con precisión conservada; componentes separados excluidos del ámbito del MVP."] if is_snit else ["Serie preprocesada con valores redondeados a dos decimales; geometría y método pendientes de validación."] if preprocessed else []),
            *(["La caché Supabase no está disponible en esta ejecución."] if cache_status == "unavailable" else []),
            *(["La serie no pudo guardarse en la caché Supabase."] if cache_status == "miss" else []),
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
