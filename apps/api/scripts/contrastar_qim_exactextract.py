"""Codex (Manuel): contraste exploratorio con exactextract 0.3.0, no validación de NASA.

Requiere exactextract instalado aparte y accesible por PYTHONPATH. No modifica la serie.
"""
import gzip
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

import netCDF4
import numpy as np
from exactextract import exact_extract
from exactextract.feature import JSONFeatureSource
from exactextract.raster import NumPyRasterSource
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.gpm_imerg import _area_weights
from scripts.explorar_qim_snit import CACHE, GEO, GEOMETRY_SHA, summarize


def main():
    version = importlib.metadata.version("exactextract")
    if version != "0.3.0":
        raise ValueError(f"Versión de exactextract no reproducida: {version}")
    sample = NumPyRasterSource(np.array([[1.0, 2.0], [3.0, 4.0]]), 0, 0, 2, 2)
    sample_geometry = JSONFeatureSource({"type": "Feature", "properties": {}, "geometry": {
        "type": "Polygon", "coordinates": [[[0, 0], [1.5, 0], [1.5, 2], [0, 2], [0, 0]]]}})
    sample_result = exact_extract(sample, sample_geometry, ["coverage", "mean"])[0]["properties"]
    if not np.allclose(sample_result["coverage"], [1, 0.5, 1, 0.5]) or not np.isclose(sample_result["mean"], 7 / 3):
        raise ValueError("Control sintético de exactextract falló")
    raw = gzip.decompress(GEO.read_bytes())
    if hashlib.sha256(raw).hexdigest() != GEOMETRY_SHA:
        raise ValueError("Geometría incompatible")
    geom = json.loads(raw)
    manifest = json.loads((CACHE / "manifest.json").read_text(encoding="utf-8"))
    expected = [f"{year:04d}-{month:02d}" for year in range(2001, 2025) for month in range(1, 13)]
    if [i["month"] for i in manifest["files"]] != expected:
        raise ValueError("Meses incompatibles")
    with netCDF4.Dataset(CACHE / manifest["files"][0]["file"]) as ds:
        grid = ds.groups["Grid"]
        lon = np.asarray(grid.variables["lon"][:], dtype=float)
        lat = np.asarray(grid.variables["lat"][:], dtype=float)
    if not (np.all(np.diff(lon) > 0) and np.all(np.diff(lat) > 0)):
        raise ValueError("Se esperaban coordenadas crecientes")
    # exactextract usa una cuadrícula regular: reconstruimos los centros nominales.
    x = np.round((lon - 0.05) * 10) / 10 + 0.05
    y = np.round((lat - 0.05) * 10) / 10 + 0.05
    if not (np.allclose(np.diff(x), 0.1, atol=1e-9) and np.allclose(np.diff(y), 0.1, atol=1e-9)):
        raise ValueError("Cuadrícula nominal incompatible")
    ids = np.arange(len(lat) * len(lon), dtype=float).reshape(len(lat), len(lon))
    raster = NumPyRasterSource(np.flipud(ids), x[0] - 0.05, y[0] - 0.05, x[-1] + 0.05, y[-1] + 0.05)
    feature = JSONFeatureSource({"type": "Feature", "properties": {}, "geometry": geom})
    props = exact_extract(raster, feature, ["values", "coverage(coverage_weight=area_spherical_m2)"])[0]["properties"]
    independent = np.zeros(ids.size)
    indices = np.asarray(props["values"], dtype=int)
    independent[indices] = np.asarray(props["coverage"], dtype=float)
    independent = independent.reshape(ids.shape)
    original, area = _area_weights(shape(geom), lat, lon)
    regular, _ = _area_weights(shape(geom), y, x)
    w1, w2 = original / original.sum(), independent / independent.sum()
    w3 = regular / regular.sum()
    qdiff, classdiff = [], []
    for item in manifest["files"]:
        path = CACHE / item["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("Recorte alterado")
        with netCDF4.Dataset(path) as ds:
            g = ds.groups["Grid"]
            if not np.array_equal(np.asarray(g.variables["lon"][:], dtype=float), lon) or not np.array_equal(np.asarray(g.variables["lat"][:], dtype=float), lat):
                raise ValueError("Grilla distinta")
            q = np.ma.filled(np.ma.asarray(g.variables["precipitationQualityIndex"][0], dtype=float), np.nan).T
            p = np.ma.filled(np.ma.asarray(g.variables["precipitation"][0], dtype=float), np.nan).T
        a = summarize(q, p, original, area)
        # Solo importan cuantiles y proporciones: la cobertura física se evalúa aparte.
        b = summarize(q, p, independent, independent.sum())
        if a["q50"] is None or b["q50"] is None:
            raise ValueError("Mes sin datos conjuntos")
        qdiff.append(abs(a["q50"] - b["q50"]))
        classdiff.append(max(abs(aa - bb) for aa, bb in zip(a["area_classes"], b["area_classes"], strict=True)))
    print(json.dumps({"months": len(qdiff), "geometry_sha256": GEOMETRY_SHA,
                      "exactextract_version": version, "exactextract_area_m2": float(independent.sum()),
                      "iyok_area_m2": float(original.sum()), "region_area_m2_epsg6933": area,
                      "normalized_weight_l1": float(np.abs(w1 - w2).sum()),
                      "normalized_weight_l1_regularized": float(np.abs(w3 - w2).sum()),
                      "max_cell_weight_abs_difference": float(np.abs(w1 - w2).max()),
                      "median_qim_abs_difference_max": max(qdiff),
                      "median_qim_different_months": sum(d > 1e-12 for d in qdiff),
                      "class_fraction_abs_difference_max": max(classdiff)}, indent=2))


if __name__ == "__main__":
    main()
