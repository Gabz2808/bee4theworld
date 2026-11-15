"""Contraste local de malla SNIT sin llamar al agregador de la API.

Ejecutar desde apps/api con .venv/Scripts/python.exe scripts/revisar_serie_snit_independiente.py.
Compara intersecciones en EPSG:6933 con centros originales y regularizados a 0,1°.
No demuestra la procedencia NASA ni valida científicamente la serie.
"""
import calendar
import gzip
import hashlib
import json
from pathlib import Path

import netCDF4
import numpy as np
from pyproj import Transformer
from shapely import (
    area,
    box,
    covers,
    intersection,
    intersects,
    prepare,
    transform,
    union_all,
)
from shapely.geometry import shape

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
CACHE = API / "data/cache/imerg-snit-2001-2024-harmony-054695e5"
GEO = ROOT / "datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz"
SERIES = ROOT / "datos/procesados/imerg-snit-continental-2001-2024-cache-v1.json"


def weighted_mean(values, valid, weights, hours):
    return float(np.sum(values[valid] * weights[valid]) / np.sum(weights[valid]) * hours)


def main():
    manifest = json.loads((CACHE / "manifest.json").read_text(encoding="utf-8"))
    series = json.loads(SERIES.read_text(encoding="utf-8"))
    raw = gzip.decompress(GEO.read_bytes())
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == series["geometry"]["geometry_sha256"]
    transform_xy = Transformer.from_crs(4326, 6933, always_xy=True).transform
    region = transform(shape(json.loads(raw)), transform_xy, interleaved=False)
    prepare(region)
    with netCDF4.Dataset(CACHE / manifest["files"][0]["file"]) as ds:
        grid = ds.groups["Grid"]
        lat = np.asarray(grid.variables["lat"][:], dtype=float)
        lon = np.asarray(grid.variables["lon"][:], dtype=float)

    def weights(y, x):
        xx, yy = np.meshgrid(x, y)
        cells = box(xx.ravel() - 0.05, yy.ravel() - 0.05, xx.ravel() + 0.05, yy.ravel() + 0.05)
        cells = transform(cells, transform_xy, interleaved=False)
        inside = covers(region, cells)
        border = intersects(region, cells) & ~inside
        weights = np.zeros(len(cells))
        weights[inside] = area(cells[inside])
        weights[border] = area(intersection(cells[border], region))
        return weights.reshape(len(y), len(x)), cells

    original, cells = weights(lat, lon)
    # Los centros de IMERG deben estar en ...05, ...15, etc.; no se altera el archivo fuente.
    regular, _ = weights(np.round((lat - 0.05) * 10) / 10 + 0.05,
                         np.round((lon - 0.05) * 10) / 10 + 0.05)
    uncovered = region.difference(union_all(cells)).area
    differences, original_differences, gaps = [], [], []
    for item, point in zip(manifest["files"], series["timeseries"], strict=True):
        path = CACHE / item["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert item["month"] == point["date"][:7]
        with netCDF4.Dataset(path) as ds:
            grid = ds.groups["Grid"]
            var = grid.variables["precipitation"]
            assert var.dimensions == ("time", "lon", "lat") and var.units == "mm/hr"
            values = np.ma.filled(np.ma.asarray(var[0, :, :], dtype=float), np.nan).T
            assert np.array_equal(np.asarray(grid.variables["lat"][:]), lat)
            assert np.array_equal(np.asarray(grid.variables["lon"][:]), lon)
        year, month = map(int, item["month"].split("-"))
        hours = 24 * calendar.monthrange(year, month)[1]
        valid = np.isfinite(values)
        original_differences.append(abs(weighted_mean(values, valid, original, hours) - point["value"]))
        differences.append(abs(weighted_mean(values, valid, regular, hours) - point["value"]))
        gaps.append(1 - float(np.sum(regular[valid]) / region.area))
    print(json.dumps({"geometry_sha256": digest, "months": len(differences),
        "original_max_abs_difference_mm": max(original_differences),
        "regular_max_abs_difference_mm": max(differences),
        "regular_median_abs_difference_mm": float(np.median(differences)),
        "original_weighted_area_fraction": float(original.sum() / region.area),
        "uncovered_area_fraction_union": uncovered / region.area,
        "regular_weighted_area_fraction": float(regular.sum() / region.area),
        "regular_valid_coverage_min": 1 - max(gaps)}, indent=2))


if __name__ == "__main__":
    main()
