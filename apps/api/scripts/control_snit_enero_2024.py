"""Consulta independiente de un mes para comprobar el procesamiento SNIT/IMERG."""
import gzip
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from dotenv import load_dotenv

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))
from app.models.geojson import GeoJSONMultiPolygon
from app.services.gpm_imerg import GPMIMERGConnector
from app.services.precipitation_processing import prepare_monthly_precipitation

GEO = ROOT / "datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz"
OUT = ROOT / "datos/procesados/imerg-snit-control-2024-01.json"


def main():
    if OUT.exists():
        raise FileExistsError("El control ya existe; no se sobrescribe")
    load_dotenv(API / ".env")
    raw = gzip.decompress(GEO.read_bytes())
    region = GeoJSONMultiPolygon.model_validate_json(raw)
    print("Iniciando extracción de control para enero de 2024.", flush=True)
    result = GPMIMERGConnector().fetch_monthly_precipitation(region, date(2024, 1, 1), date(2024, 1, 31))
    frame = prepare_monthly_precipitation(result, date(2024, 1, 1), date(2024, 1, 31))
    row = frame.iloc[0]
    output = {"source": "NASA GES DISC CMR/Harmony", "dataset": result.dataset, "accessed_at_utc": datetime.now(UTC).isoformat(),
              "geometry_sha256": hashlib.sha256(raw).hexdigest(), "source_units": result.source_units, "unit": result.output_units,
              "weighting_method": result.weighting_method, "granule_ids": list(result.granule_ids), "date": "2024-01-01",
              "value": float(row.precipitation_mm), "coverage_fraction": float(row.coverage_fraction), "quality_flag": row.quality_flag}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("x", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(f"Control guardado: {OUT}; cobertura: {output['coverage_fraction']:.6f}", flush=True)


if __name__ == "__main__":
    main()
