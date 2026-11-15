"""Codex (Manuel): exploración local de QIm; no modifica la API ni valida el índice."""
import gzip
import hashlib
import json
import sys
from pathlib import Path

import netCDF4
import numpy as np
from shapely.geometry import shape

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))
from app.services.gpm_imerg import _area_weights

CACHE = API / "data/cache/imerg-snit-2001-2024-harmony-054695e5"
GEO = ROOT / "datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz"
GEOMETRY_SHA = "ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb"


def summarize(q, precip, weights, region_area):
    """Cuantiles por inversa de distribución acumulada ponderada por área."""
    q, precip, weights = (np.asarray(a, dtype=float) for a in (q, precip, weights))
    if q.shape != precip.shape or q.shape != weights.shape or region_area <= 0:
        raise ValueError("Grilla o área incompatible")
    if not np.isfinite(weights).all() or np.any(weights < 0):
        raise ValueError("Pesos inválidos")
    if weights.sum() / region_area > 1.00001:
        raise ValueError("La suma de áreas excede el territorio; revisar cuadrícula")
    q_ok = np.isfinite(q) & (q >= 0) & (weights > 0)
    p_ok = np.isfinite(precip) & (precip >= 0) & (weights > 0)
    valid = q_ok & p_ok
    base = {"coverage_precip": float(weights[p_ok].sum() / region_area),
            "coverage_qim": float(weights[q_ok].sum() / region_area),
            "coverage_joint": float(weights[valid].sum() / region_area)}
    if not valid.any():
        return {**base, "q10": None, "q50": None, "q90": None, "area_classes": None}
    values, w = q[valid], weights[valid]
    order = np.argsort(values, kind="stable")
    values, w = values[order], w[order]
    cumulative = np.cumsum(w)
    total = float(cumulative[-1])
    quantiles = [float(values[np.searchsorted(cumulative, total * p, side="left")]) for p in (0.1, 0.5, 0.9)]
    fractions = [float(w[values < 3].sum() / total), float(w[(values >= 3) & (values < 10)].sum() / total), float(w[values >= 10].sum() / total)]
    return {**base, "q10": quantiles[0], "q50": quantiles[1], "q90": quantiles[2], "area_classes": fractions}


def main():
    manifest_bytes = (CACHE / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    raw = gzip.decompress(GEO.read_bytes())
    if hashlib.sha256(raw).hexdigest() != GEOMETRY_SHA:
        raise ValueError("Huella de geometría incorrecta")
    records, weights, lat, lon = [], None, None, None
    files = manifest["files"]
    expected = [f"{year:04d}-{month:02d}" for year in range(2001, 2025) for month in range(1, 13)]
    if [x["month"] for x in files] != expected:
        raise ValueError("Meses incompletos o desordenados")
    for item in files:
        path = CACHE / item["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Huella incorrecta: {path.name}")
        with netCDF4.Dataset(path) as ds:
            grid = ds.groups["Grid"]
            x = np.asarray(grid.variables["lon"][:], dtype=float)
            y = np.asarray(grid.variables["lat"][:], dtype=float)
            if weights is None:
                lon, lat = x, y
                weights, region_area = _area_weights(shape(json.loads(raw)), lat, lon)
            elif not np.array_equal(x, lon) or not np.array_equal(y, lat):
                raise ValueError("Cuadrícula inconsistente")
            t = grid.variables["time"]
            date = netCDF4.num2date(t[:], t.units, calendar=getattr(t, "calendar", "standard"))
            if len(date) != 1 or f"{date[0].year:04d}-{date[0].month:02d}" != item["month"]:
                raise ValueError("Fecha incompatible")
            q, p = grid.variables["precipitationQualityIndex"], grid.variables["precipitation"]
            if q.dimensions != ("time", "lon", "lat") or p.dimensions != q.dimensions or p.units != "mm/hr":
                raise ValueError("Dimensiones o unidades inesperadas")
            qv = np.ma.filled(np.ma.asarray(q[0], dtype=float), np.nan).T
            pv = np.ma.filled(np.ma.asarray(p[0], dtype=float), np.nan).T
            records.append({"month": item["month"], **summarize(qv, pv, weights, region_area)})
    print(json.dumps({"status": "exploratorio_no_validado", "geometry_sha256": GEOMETRY_SHA,
                      "dataset": "GPM_3IMERGM.07", "source": "NASA GES DISC CMR/Harmony",
                      "harmony_job_id": manifest["job_id"], "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                      "spatial_method": "área de intersección de celda y geometría SNIT en EPSG:6933",
                      "category_reference": "IMERG V07 ATBD 2023 sección 9.5; elección experimental, no filtro",
                      "categories": ["0<=q<3", "3<=q<10", "q>=10"],
                      "quantiles": "inversa de distribución acumulada ponderada por área", "months": records}, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
