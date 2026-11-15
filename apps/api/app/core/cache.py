from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.security import is_write_authorized
from app.models.exploration import ExplorationRequest
from app.models.geojson import GeoJSONPolygon, are_geometries_equal
from app.services.gpm_imerg import GPMIMERGResult

logger = logging.getLogger(__name__)

CACHE_DIR_DEFAULT = Path(__file__).resolve().parents[2] / "data" / "cache"

DEFAULT_PRODUCT_VERSION = "v07"
DEFAULT_PROCESSING_VERSION = "p1"


def get_cache_dir() -> Path:
    cache_dir = CACHE_DIR_DEFAULT
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def make_cache_key(
    variable_id: str,
    region_id: str,
    geom: GeoJSONPolygon,
    start: date,
    end: date,
    product_version: str = DEFAULT_PRODUCT_VERSION,
    processing_version: str = DEFAULT_PROCESSING_VERSION,
) -> str:
    """Genera una clave determinista que versiona producto, procesamiento, datos y geometría."""
    geom_str = json.dumps(geom.coordinates, sort_keys=True)
    geom_hash = hashlib.sha256(geom_str.encode("utf-8")).hexdigest()[:16]
    sanitized_region = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in region_id
    )[:30]
    return (
        f"{variable_id}_{product_version}_{processing_version}_{sanitized_region}_"
        f"{geom_hash}_{start.isoformat()}_{end.isoformat()}.json"
    )


def make_legacy_cache_key(
    variable_id: str,
    region_id: str,
    geom: GeoJSONPolygon,
    start: date,
    end: date,
) -> str:
    """Clave compatible anterior sin versionamiento de producto/procesamiento."""
    geom_str = json.dumps(geom.coordinates, sort_keys=True)
    geom_hash = hashlib.sha256(geom_str.encode("utf-8")).hexdigest()[:16]
    sanitized_region = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in region_id
    )[:30]
    return f"{variable_id}_{sanitized_region}_{geom_hash}_{start.isoformat()}_{end.isoformat()}.json"


def load_from_cache(
    variable_id: str,
    region_id: str,
    geom: GeoJSONPolygon,
    start: date,
    end: date,
    product_version: str = DEFAULT_PRODUCT_VERSION,
    processing_version: str = DEFAULT_PROCESSING_VERSION,
    with_provenance: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, Any]] | None:
    """Carga datos y procedencia desde la caché local.

    Aplica recuperación automática ante caché incompleta o corrupta (eliminando el archivo)
    y admite retrocompatibilidad con formato legacy.
    """
    cache_key = make_cache_key(
        variable_id, region_id, geom, start, end, product_version, processing_version
    )
    cache_dir = get_cache_dir()
    cache_file = cache_dir / cache_key

    # Si no existe clave versionada, verificar clave legacy
    is_legacy = False
    if not cache_file.exists():
        legacy_key = make_legacy_cache_key(variable_id, region_id, geom, start, end)
        legacy_file = cache_dir / legacy_key
        if legacy_file.exists():
            cache_file = legacy_file
            is_legacy = True
        else:
            return None

    expected_months = pd.date_range(start=start, end=end, freq="MS")

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            raw_content = json.load(f)

        # Formato schema 2.0 con preservación explícita de procedencia
        if isinstance(raw_content, dict) and "records" in raw_content:
            records = raw_content.get("records", [])
            # Recuperación ante caché incompleta: si no contiene todos los meses requeridos
            if len(records) != len(expected_months):
                logger.warning(
                    "Caché incompleta para %s: se esperaban %d meses pero contiene %d. Descartando y purgando.",
                    cache_key,
                    len(expected_months),
                    len(records),
                )
                cache_file.unlink(missing_ok=True)
                return None

            provenance = raw_content.get("provenance", {})
            parsed_rows = {}
            for r in records:
                m = pd.Timestamp(r["month"])
                val = (
                    float(r["precipitation_mm"])
                    if r.get("precipitation_mm") is not None
                    else float("nan")
                )
                cov = float(r.get("coverage_fraction", 1.0))
                flag = str(r.get("quality_flag", "ok"))
                parsed_rows[m] = (val, cov, flag)

            df = pd.DataFrame.from_dict(
                parsed_rows,
                orient="index",
                columns=("precipitation_mm", "coverage_fraction", "quality_flag"),
            ).reindex(expected_months)
            df.index.name = "month"

            # Adjuntar procedencia a los atributos del DataFrame
            df.attrs["provenance"] = provenance
            logger.info("Cache hit v2 para clave %s con procedencia explícita", cache_key)
            if with_provenance:
                return df, provenance
            return df

        # Soporte para caché legacy orient="table"
        df = pd.read_json(cache_file, orient="table")
        if (
            len(df) == len(expected_months)
            and df.index.min() == expected_months.min()
            and df.index.max() == expected_months.max()
        ):
            logger.info("Cache hit legacy para clave %s", cache_key)
            df.attrs["provenance"] = {}
            if with_provenance:
                return df, {}
            return df

        # Incompleta en legacy: descartar y purgar
        logger.warning("Caché legacy incompleta para %s. Purgando.", cache_key)
        cache_file.unlink(missing_ok=True)
        return None
    except Exception as e:  # noqa: BLE001 - boundary fallback
        logger.warning(
            "Error leyendo o parseando archivo de caché %s: %s. Eliminando archivo corrupto.",
            cache_file,
            e,
        )
        try:
            cache_file.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def save_to_cache(
    variable_id: str,
    region_id: str,
    geom: GeoJSONPolygon,
    start: date,
    end: date,
    df: pd.DataFrame,
    provenance: dict[str, Any] | None = None,
    product_version: str = DEFAULT_PRODUCT_VERSION,
    processing_version: str = DEFAULT_PROCESSING_VERSION,
) -> None:
    """Guarda serie y procedencia completa usando escritura atómica protegida contra concurrencia."""
    cache_key = make_cache_key(
        variable_id, region_id, geom, start, end, product_version, processing_version
    )
    cache_dir = get_cache_dir()
    cache_file = cache_dir / cache_key
    unique_suffix = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
    temp_file = cache_dir / f".tmp_{unique_suffix}_{cache_key}"

    try:
        records = []
        for month_ts, row in df.iterrows():
            val = (
                None
                if pd.isna(row["precipitation_mm"])
                else float(row["precipitation_mm"])
            )
            records.append(
                {
                    "month": month_ts.strftime("%Y-%m-%d"),
                    "precipitation_mm": val,
                    "coverage_fraction": float(row["coverage_fraction"]),
                    "quality_flag": str(row["quality_flag"]),
                }
            )

        payload = {
            "format": "iyok_cache_v2",
            "schema_version": "2.0",
            "product_version": product_version,
            "processing_version": processing_version,
            "variable_id": variable_id,
            "region_id": region_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "geom_coordinates": geom.coordinates,
            "provenance": provenance or {},
            "records": records,
        }

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Reemplazo atómico en POSIX: evita colisiones de concurrencia y lecturas parciales
        temp_file.replace(cache_file)
        logger.info("Datos y procedencia guardados en caché local %s", cache_file)
    except Exception as e:  # noqa: BLE001 - boundary fallback
        logger.warning("Error guardando en caché %s: %s", cache_file, e)
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)


def invalidate_cache(
    variable_id: str,
    region_id: str,
    geom: GeoJSONPolygon,
    start: date,
    end: date,
    product_version: str = DEFAULT_PRODUCT_VERSION,
    processing_version: str = DEFAULT_PROCESSING_VERSION,
) -> bool:
    """Invalida y purga explícitamente un archivo de caché."""
    cache_key = make_cache_key(
        variable_id, region_id, geom, start, end, product_version, processing_version
    )
    cache_dir = get_cache_dir()
    cache_file = cache_dir / cache_key
    deleted = False
    if cache_file.exists():
        cache_file.unlink(missing_ok=True)
        deleted = True
        logger.info("Caché invalidada y eliminada para %s", cache_key)

    legacy_key = make_legacy_cache_key(variable_id, region_id, geom, start, end)
    legacy_file = cache_dir / legacy_key
    if legacy_file.exists():
        legacy_file.unlink(missing_ok=True)
        deleted = True

    return deleted


def save_to_supabase(
    supabase: Any,
    request: ExplorationRequest,
    geom: GeoJSONPolygon,
    result: GPMIMERGResult,
    monthly_frame: pd.DataFrame,
    region_identifier: str,
) -> None:
    """Intenta persistir el resultado de ingestión y la serie procesada en Supabase.

    Satisface estrictamente los criterios de integridad:
    1. Geometría personalizada nunca se asocia por defecto a otra región;
       se conserva fuera de Supabase (en caché local) a menos que posea identidad verificada.
    2. Escritura atómica con rollback en caso de fallo parcial para evitar lecturas de datos truncados.
    3. Idempotencia y selección determinista.
    """
    if supabase is None:
        return

    # Comprobación de autorización de escritura
    if not is_write_authorized():
        logger.info("Persistencia en Supabase no autorizada en este entorno.")
        return

    # Criterio 1: Polígono personalizado se conserva fuera de Supabase para evitar asociaciones indebidas
    if region_identifier == "custom-polygon" or request.region is not None:
        logger.info(
            "Geometría personalizada ('%s') sin registro verificado en catálogo oficial. "
            "Se conserva en caché local fuera de Supabase para evitar asociarla a otra región.",
            region_identifier,
        )
        return

    try:
        region_uuid: str | None = None
        registered_geom: dict | None = None
        if len(region_identifier) == 36 and "-" in region_identifier:
            res = (
                supabase.table("regions")
                .select("id, name, geom")
                .eq("id", region_identifier)
                .limit(1)
                .execute()
            )
            if res.data:
                region_uuid = str(res.data[0]["id"])
                registered_geom = res.data[0].get("geom")
        else:
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
                    registered_geom = res.data[0].get("geom")
                    break

        if not region_uuid:
            logger.debug(
                "Región '%s' no encontrada con identidad verificada en Supabase; se mantiene en caché local.",
                region_identifier,
            )
            return

        if registered_geom and not are_geometries_equal(registered_geom, geom):
            logger.warning(
                "Incompatibilidad geométrica: La geometría para '%s' difiere de la registrada en Supabase. Omitiendo persistencia.",
                region_identifier,
            )
            return

        geom_payload = geom.model_dump()
        start = request.start_date.isoformat()  # type: ignore[union-attr]
        end = request.end_date.isoformat()      # type: ignore[union-attr]

        # Idempotencia: Verificar si ya existe un run idéntico y completo
        existing_runs = (
            supabase.table("ingestion_runs")
            .select("id")
            .eq("region_id", region_uuid)
            .eq("variable_id", request.variable_id)
            .eq("requested_start", start)
            .eq("requested_end", end)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if existing_runs.data:
            existing_run_id = existing_runs.data[0]["id"]
            existing_data = (
                supabase.table("processed_data")
                .select("observed_month")
                .eq("ingestion_run_id", existing_run_id)
                .execute()
            )
            if len(existing_data.data) == len(monthly_frame):
                logger.info(
                    "Ingestión idéntica y completa ya existe en Supabase (%s); omitiendo duplicación.",
                    existing_run_id,
                )
                return

        run_payload = {
            "region_id": region_uuid,
            "variable_id": request.variable_id,
            "requested_start": start,
            "requested_end": end,
            "dataset_id": result.dataset,
            "dataset_version": result.version,
            "source_units": result.source_units,
            "output_units": result.output_units,
            "unit_conversion": result.unit_conversion,
            "spatial_resolution_degrees": float(result.spatial_resolution_degrees),
            "weighting_method": result.weighting_method,
            "source_granule_ids": list(result.granule_ids),
            "region_geometry_snapshot": geom_payload,
            "region_source_snapshot": getattr(result, "effective_origin", "NASA Harmony"),
            "region_version_snapshot": "1.0",
        }

        run_res = supabase.table("ingestion_runs").insert(run_payload).execute()
        if not run_res.data:
            return

        run_id = run_res.data[0]["id"]
        processed_rows = []
        for month_ts, row in monthly_frame.iterrows():
            val = (
                float(row["precipitation_mm"])
                if pd.notna(row["precipitation_mm"])
                else None
            )
            processed_rows.append(
                {
                    "ingestion_run_id": run_id,
                    "observed_month": month_ts.date().isoformat(),
                    "precipitation_mm": val,
                    "coverage_fraction": float(row["coverage_fraction"]),
                    "quality_flag": str(row["quality_flag"]),
                }
            )

        # Inserción con rollback defensivo para garantizar atomicidad
        try:
            if processed_rows:
                data_res = supabase.table("processed_data").insert(processed_rows).execute()
                if not data_res.data or len(data_res.data) != len(processed_rows):
                    raise RuntimeError("Inserción incompleta o truncada en processed_data")
            logger.info(
                "Persistido en Supabase run_id %s con %d registros.",
                run_id,
                len(processed_rows),
            )
        except Exception as insert_err:
            logger.error(
                "Error insertando processed_data para run_id %s; aplicando rollback defensivo: %s",
                run_id,
                insert_err,
            )
            try:
                supabase.table("ingestion_runs").delete().eq("id", run_id).execute()
            except Exception as rollback_err:  # noqa: BLE001 - boundary fallback
                logger.error("Error durante rollback de ingestion_run %s: %s", run_id, rollback_err)
            raise
    except Exception as e:  # noqa: BLE001 - boundary fallback
        logger.warning("No se pudo persistir en Supabase: %s", e)
