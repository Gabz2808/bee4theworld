"""Genera serie exploratoria IMERG para el componente continental principal SNIT.

No modifica el catálogo ni la serie de la aplicación. Requiere EARTHDATA_TOKEN en .env.
Ejecutar desde apps/api: .venv/Scripts/python.exe -u scripts/generar_serie_snit.py
"""
import gzip
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from dotenv import load_dotenv
from pyproj import Transformer
from shapely import transform
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

API = Path(__file__).resolve().parents[1]
ROOT = API.parents[1]
sys.path.insert(0, str(API))
from app.models.geojson import GeoJSONMultiPolygon
from app.services.gpm_imerg import GPMIMERGConnector
from app.services.precipitation_processing import prepare_monthly_precipitation
from capturar_frontera_snit import DATA, META, verify

OUTPUT = ROOT / "datos" / "procesados" / "imerg-snit-continental-2001-2024-v1.json"
GEO = ROOT / "datos" / "fuentes" / "snit-provincial-2026-11-15" / "continental-principal.geojson.gz"
START, END = date(2001, 1, 1), date(2024, 12, 31)


def main():
    if OUTPUT.exists():
        raise FileExistsError("Ya existe una serie; no se sobrescribe")
    load_dotenv(API / ".env")
    verify()
    metadata = json.loads(META.read_text(encoding="utf-8"))
    data = json.loads(gzip.decompress(DATA.read_bytes()).decode("utf-8"))
    whole = unary_union([shape(f["geometry"]) for f in data["features"]])
    project = Transformer.from_crs(4326, 6933, always_xy=True).transform
    components = list(whole.geoms)
    main_part = max(components, key=lambda p: transform(p, project, interleaved=False).area)
    region = GeoJSONMultiPolygon.model_validate(mapping(type(whole)([main_part])))
    geo_raw = json.dumps(region.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    geo_hash = hashlib.sha256(geo_raw).hexdigest()
    excluded_area = sum(transform(p, project, interleaved=False).area for p in components if p is not main_part)
    GEO.parent.mkdir(parents=True, exist_ok=True)
    if GEO.exists():
        if gzip.decompress(GEO.read_bytes()) != geo_raw:
            raise ValueError("La geometría existente no coincide; no se sobrescribe")
    else:
        with GEO.open("xb") as f:
            f.write(gzip.compress(geo_raw, mtime=0))
    print(f"Geometría congelada: SHA-256 {geo_hash}; componentes excluidos: {len(components)-1}; área excluida {excluded_area/1e6:.2f} km²", flush=True)
    print("Consultando 288 meses a CMR/Harmony; el trabajo remoto puede tardar varios minutos.", flush=True)
    result = GPMIMERGConnector().fetch_monthly_precipitation(region, START, END)
    frame = prepare_monthly_precipitation(result, START, END)
    if len(frame) != 288 or frame.precipitation_mm.isna().any() or len(result.granule_ids) != 288 or len(set(result.granule_ids)) != 288:
        raise ValueError("La serie no está completa y no se publicará")
    output = {
        "status": "serie exploratoria; interpretación estadística y revisión territorial pendientes",
        "source": "NASA GES DISC CMR/Harmony", "dataset": result.dataset, "version": result.version,
        "collection_concept_id": "C2723754851-GES_DISC", "doi": "10.5067/GPM/IMERG/3B-MONTH/07",
        "accessed_at_utc": datetime.now(UTC).isoformat(), "period": {"start": START.isoformat(), "end": END.isoformat()},
        "geometry": {"source": "IGN / Registro Nacional / SNIT", "source_snapshot_sha256": metadata["sha256_geojson"],
            "geometry_sha256": geo_hash, "selection": "componente de mayor área de la unión provincial; excluye 120 componentes separados",
            "excluded_area_km2": excluded_area / 1e6, "crs": "EPSG:4326", "file": str(GEO.relative_to(ROOT)).replace("\\", "/"),
            "note": "Alcance continental operativo: no se clasificaron individualmente islas ni masas interiores."},
        "source_units": result.source_units, "unit": result.output_units, "unit_conversion": result.unit_conversion,
        "weighting_method": result.weighting_method, "spatial_resolution_degrees": result.spatial_resolution_degrees,
        "granule_ids": list(result.granule_ids),
        "timeseries": [{"date": index.date().isoformat(), "value": float(row.precipitation_mm),
                        "coverage_fraction": float(row.coverage_fraction), "quality_flag": row.quality_flag} for index, row in frame.iterrows()],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("x", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print(f"Serie guardada: {OUTPUT}, {len(frame)} meses; huella geométrica {geo_hash}", flush=True)


if __name__ == "__main__":
    main()
