"""Procesa recortes mensuales Harmony conservados localmente, sin descargar de nuevo."""
import calendar
import argparse
import gzip
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import shape

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))
from app.services.gpm_imerg import GPMIMERGConnector, _aggregate_dataset

CACHE = API / "data/cache/imerg-snit-2001-2024-harmony-054695e5"
GEO = ROOT / "datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz"
ORIGINAL = ROOT / "docs/evidencia/harmony-costa-rica-provisional-2001-2024.json"
OUT = ROOT / "datos/procesados/imerg-snit-continental-2001-2024-cache-v1.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=CACHE, help="Directorio de recortes verificados o restaurados")
    parser.add_argument("--output", type=Path, default=OUT, help="Destino nuevo para la serie")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("La serie ya existe; no se sobrescribe")
    manifest = json.loads((args.cache / "manifest.json").read_text(encoding="utf-8"))
    geo = gzip.decompress(GEO.read_bytes())
    records, lat, lon = {}, None, None
    for item in manifest["files"]:
        path = args.cache / item["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Archivo alterado: {path.name}")
        with netCDF4.Dataset(path) as ds:
            grid = ds.groups["Grid"]
            var = grid.variables["precipitation"]
            if var.dimensions != ("time", "lon", "lat") or var.units != "mm/hr":
                raise ValueError("Dimensiones o unidades inesperadas")
            lat_new, lon_new = np.asarray(grid.variables["lat"][:]), np.asarray(grid.variables["lon"][:])
            if lat is None:
                lat, lon = lat_new, lon_new
            elif not np.array_equal(lat, lat_new) or not np.array_equal(lon, lon_new):
                raise ValueError("Las cuadrículas mensuales no coinciden")
            time = grid.variables["time"]
            observed = netCDF4.num2date(time[:], time.units, calendar=getattr(time, "calendar", "standard"))
            if len(observed) != 1:
                raise ValueError("Se esperaba un solo mes por archivo")
            month = f"{observed[0].year:04d}-{observed[0].month:02d}"
            if month != item["month"] or month in records:
                raise ValueError("Mes duplicado o incompatible con el manifiesto")
            records[month] = np.ma.filled(np.ma.asarray(var[0, :, :], dtype=float), np.nan).T
    months = pd.date_range("2001-01-01", "2024-12-01", freq="MS")
    if sorted(records) != [m.strftime("%Y-%m") for m in months]:
        raise ValueError("La caché no contiene exactamente los 288 meses")
    ds = xr.Dataset({"precipitation": (("time", "lat", "lon"), np.stack([records[m.strftime("%Y-%m")] for m in months]), {"units": "mm/hr"})}, coords={"time": months, "lat": lat, "lon": lon})
    source_units, observations = _aggregate_dataset(ds, shape(json.loads(geo)), tuple(m.date() for m in months))
    previous = json.loads(ORIGINAL.read_text(encoding="utf-8"))
    granules = GPMIMERGConnector()._search_granules(months[0].date(), pd.Timestamp("2024-12-31").date(), tuple(m.date() for m in months))
    ids = [g["id"] for g in granules]
    if ids != previous["metadata"]["source_granule_ids"]:
        raise ValueError("Los gránulos CMR ya no coinciden con la extracción anterior; investigar")
    points = []
    for item in observations:
        if item.value is None or not math.isfinite(item.value) or item.value < 0:
            raise ValueError("Valor de precipitación ausente o inválido")
        value = item.value * 24 * calendar.monthrange(item.month.year, item.month.month)[1]
        points.append({"date": item.month.isoformat(), "value": value, "coverage_fraction": item.coverage_fraction, "quality_flag": "ok" if item.coverage_fraction == 1 else "partial_coverage"})
    output = {"status": "serie exploratoria; interpretación estadística y revisión territorial pendientes", "source": "NASA GES DISC CMR/Harmony, recortes locales verificados", "dataset": "GPM_3IMERGM.07", "version": "07", "collection_concept_id": "C2723754851-GES_DISC", "doi": "10.5067/GPM/IMERG/3B-MONTH/07", "processed_at_utc": datetime.now(UTC).isoformat(), "harmony_job_id": manifest["job_id"],
              "geometry": {"geometry_sha256": hashlib.sha256(geo).hexdigest(), "file": str(GEO.relative_to(ROOT)).replace("\\", "/"), "selection": "componente principal de la unión provincial IGN/SNIT; componentes separados excluidos"},
              "source_units": source_units, "unit": "mm/month", "unit_conversion": "tasa mm/hr multiplicada por las horas del mes", "weighting_method": "intersección parcial de celdas en EPSG:6933", "granule_ids": ids, "granule_ids_provenance": "consulta CMR comprobada frente a extracción previa; nombres mensuales de Harmony verificados", "timeseries": points}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(f"Serie procesada desde la caché: {args.output}; {len(points)} meses")


if __name__ == "__main__":
    main()
