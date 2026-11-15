"""Caché de series IMERG sobre el esquema existente, sin alterar otras ingestas."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from shapely import from_wkb
from shapely.geometry import shape

from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import GPMIMERGResult

logger = logging.getLogger(__name__)
DATASET = "GPM_3IMERGM.07"
VERSION = "07"
# La versión de región identifica también el contrato de procesamiento de esta caché.
REGION_SOURCE = "Iyök: geometría aproximada no verificada; NASA CMR/Harmony"
REGION_VERSION = "provisional; cache-nasa-v1"


@dataclass(frozen=True)
class CachedSeries:
    frame: pd.DataFrame
    metadata: dict[str, Any]


def _geometry(value: Any):
    if isinstance(value, str):
        return from_wkb(bytes.fromhex(value.removeprefix("\\x")))
    return shape(value)


def _region_id(client: Any, public_id: str, geom: GeoJSONPolygon) -> str | None:
    # No asignar un polígono arbitrario a la región predefinida.
    if public_id != "costa-rica-continental":
        return None
    response = client.table("regions").select("id,name,geom").eq("name", "Costa Rica Continental").limit(2).execute()
    if len(response.data) != 1:
        return None
    region = response.data[0]
    if not _geometry(region["geom"]).equals(shape(geom.model_dump(mode="json"))):
        return None
    return str(region["id"])


def _rows_to_frame(rows: list[dict[str, Any]], start: date, end: date) -> pd.DataFrame | None:
    expected = pd.date_range(start=start, end=end, freq="MS", name="month")
    records: dict[pd.Timestamp, tuple[float | None, float, str]] = {}
    for row in rows:
        month = pd.Timestamp(row["observed_month"])
        value = row["precipitation_mm"]
        coverage = float(row["coverage_fraction"])
        flag = row["quality_flag"]
        if month.day != 1 or month in records or month not in expected:
            return None
        if value is not None and (not math.isfinite(float(value)) or float(value) < 0):
            return None
        if not math.isfinite(coverage) or not 0 <= coverage <= 1 or flag not in {"ok", "partial_coverage", "missing_value", "missing_month"}:
            return None
        if (value is None) != (flag in {"missing_value", "missing_month"}):
            return None
        if (flag == "ok" and coverage != 1) or (flag == "partial_coverage" and not 0 < coverage < 1) or (flag == "missing_month" and coverage != 0):
            return None
        records[month] = (float(value) if value is not None else None, coverage, flag)
    if set(records) != set(expected):
        return None
    frame = pd.DataFrame.from_dict(records, orient="index", columns=["precipitation_mm", "coverage_fraction", "quality_flag"]).reindex(expected)
    frame.index.name = "month"
    frame["precipitation_mm"] = pd.to_numeric(frame["precipitation_mm"], errors="coerce")
    return frame


def load_supabase_series(client: Any, public_id: str, geom: GeoJSONPolygon, start: date, end: date) -> CachedSeries | None:
    try:
        region_id = _region_id(client, public_id, geom)
        if not region_id:
            return None
        result = (client.table("ingestion_runs")
            .select("id,requested_start,requested_end,dataset_id,dataset_version,source_units,output_units,unit_conversion,spatial_resolution_degrees,weighting_method,source_granule_ids,region_geometry_snapshot,region_source_snapshot,region_version_snapshot,created_at")
            .eq("region_id", region_id).eq("variable_id", "precipitation")
            .eq("dataset_id", DATASET).eq("dataset_version", VERSION).eq("output_units", "mm/month")
            .eq("region_source_snapshot", REGION_SOURCE).eq("region_version_snapshot", REGION_VERSION)
            .lte("requested_start", start.isoformat()).gte("requested_end", end.isoformat())
            .order("created_at", desc=True).limit(20).execute())
        expected_geom = shape(geom.model_dump(mode="json"))
        for run in result.data:
            if not _geometry(run["region_geometry_snapshot"]).equals(expected_geom):
                continue
            if not all(run.get(k) for k in ("source_units", "unit_conversion", "weighting_method", "source_granule_ids", "created_at")):
                continue
            if run["source_units"] != "mm/hr" or not math.isclose(float(run["spatial_resolution_degrees"]), 0.1, rel_tol=0, abs_tol=1e-9):
                continue
            full_start = date.fromisoformat(run["requested_start"])
            full_end = date.fromisoformat(run["requested_end"])
            expected_count = len(pd.date_range(start=full_start, end=full_end, freq="MS"))
            ids = run["source_granule_ids"]
            if not isinstance(ids, list) or len(ids) != expected_count or not all(isinstance(x, str) and x for x in ids) or len(set(ids)) != expected_count:
                continue
            rows = (client.table("processed_data").select("observed_month,precipitation_mm,coverage_fraction,quality_flag")
                .eq("ingestion_run_id", run["id"]).order("observed_month").limit(1000).execute()).data
            frame = _rows_to_frame(rows, full_start, full_end)
            if frame is None:
                continue
            return CachedSeries(frame.loc[start.isoformat():end.isoformat()].copy(), run)
    except Exception:  # noqa: BLE001 - boundary fallback
        logger.warning("No se pudo leer la caché Supabase; se consultará la fuente de datos.")
    return None


def save_supabase_series(client: Any, public_id: str, geom: GeoJSONPolygon, start: date, end: date, result: GPMIMERGResult, frame: pd.DataFrame) -> bool:
    try:
        region_id = _region_id(client, public_id, geom)
        if not region_id or result.dataset != DATASET or result.version != VERSION or result.source_units != "mm/hr" or result.output_units != "mm/month" or not math.isclose(result.spatial_resolution_degrees, 0.1, rel_tol=0, abs_tol=1e-9):
            return False
        if not shape(result.region.model_dump(mode="json")).equals(shape(geom.model_dump(mode="json"))):
            return False
        expected = pd.date_range(start=start, end=end, freq="MS")
        if not frame.index.equals(expected) or len(result.granule_ids) != len(expected) or len(set(result.granule_ids)) != len(expected) or not all(result.granule_ids):
            return False
        rows = []
        for month, row in frame.iterrows():
            rows.append({"observed_month": month.date().isoformat(), "precipitation_mm": float(row["precipitation_mm"]) if pd.notna(row["precipitation_mm"]) else None,
                "coverage_fraction": float(row["coverage_fraction"]), "quality_flag": str(row["quality_flag"])})
        if _rows_to_frame(rows, start, end) is None:
            return False
        geom_wkt = "SRID=4326;" + shape(geom.model_dump(mode="json")).wkt
        payload = {"region_id": region_id, "variable_id": "precipitation", "requested_start": start.isoformat(), "requested_end": end.isoformat(),
            "dataset_id": DATASET, "dataset_version": VERSION, "source_units": result.source_units, "output_units": result.output_units,
            "unit_conversion": result.unit_conversion, "spatial_resolution_degrees": result.spatial_resolution_degrees,
            "weighting_method": result.weighting_method, "source_granule_ids": list(result.granule_ids),
            "region_geometry_snapshot": geom_wkt, "region_source_snapshot": REGION_SOURCE, "region_version_snapshot": REGION_VERSION}
        response = client.table("ingestion_runs").insert(payload).execute()
        if not response.data:
            return False
        run_id = response.data[0]["id"]
        client.table("processed_data").insert([{**row, "ingestion_run_id": run_id} for row in rows]).execute()
        # Verificación de esta ingesta: las escrituras son dos transacciones separadas.
        stored = (client.table("processed_data").select("observed_month,precipitation_mm,coverage_fraction,quality_flag")
            .eq("ingestion_run_id", run_id).order("observed_month").limit(1000).execute()).data
        return _rows_to_frame(stored, start, end) is not None
    except Exception:  # noqa: BLE001 - boundary fallback
        logger.warning("No se pudo guardar la serie en la caché Supabase.")
        return False
