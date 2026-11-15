"""Comprueba la serie SNIT y la compara con la serie provisional sin asignar causalidad."""
import gzip
import argparse
import hashlib
import json
import math
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SERIES = ROOT / "datos/procesados/imerg-snit-continental-2001-2024-v1.json"
OLD = ROOT / "docs/evidencia/harmony-costa-rica-provisional-2001-2024.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("series", nargs="?", type=Path, default=SERIES)
    data = json.loads(parser.parse_args().series.read_text(encoding="utf-8"))
    geo = gzip.decompress((ROOT / data["geometry"]["file"]).read_bytes())
    if hashlib.sha256(geo).hexdigest() != data["geometry"]["geometry_sha256"]:
        raise ValueError("La huella de la geometría no coincide")
    points, ids = data["timeseries"], data["granule_ids"]
    expected = pd.date_range("2001-01-01", "2024-12-01", freq="MS")
    if [p["date"] for p in points] != [d.date().isoformat() for d in expected] or len(ids) != 288 or len(set(ids)) != 288:
        raise ValueError("Los meses o gránulos están incompletos o duplicados")
    if any(not math.isfinite(p["value"]) or p["value"] < 0 or not 0 <= p["coverage_fraction"] <= 1 for p in points):
        raise ValueError("Hay valores o coberturas inválidos")
    previous = json.loads(OLD.read_text(encoding="utf-8"))
    if previous["metadata"]["source_granule_ids"] != ids:
        raise ValueError("Los identificadores de gránulos difieren de la extracción anterior; investigar antes de comparar")
    old = {p["date"]: p["value"] for p in previous["timeseries"]}
    diffs = [p["value"] - old[p["date"]] for p in points]
    print("Meses consecutivos:", len(points), "gránulos únicos:", len(set(ids)), "cobertura mínima:", min(p["coverage_fraction"] for p in points))
    print("Diferencia frente al polígono provisional (mm/mes): mediana absoluta", round(float(pd.Series(diffs).abs().median()), 2), "máxima absoluta", round(max(map(abs, diffs)), 2))
    print("La serie anterior está redondeada; diferencias incluyen el cambio de geometría y el redondeo.")


if __name__ == "__main__":
    main()
