"""Captura inmutable y validación local de una respuesta WFS IGN/SNIT.

Ejecutar desde apps/api: .venv/Scripts/python.exe scripts/capturar_frontera_snit.py capture
Verificar: .venv/Scripts/python.exe scripts/capturar_frontera_snit.py verify
La captura es una fuente candidata; no define el área de análisis ni modifica la API.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from shapely.geometry import shape

URL = "https://geos.snitcr.go.cr/be/IGN_5_CO/wfs"
PARAMS = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "IGN_5_CO:limiteprovincial_5k", "outputFormat": "application/json", "srsName": "EPSG:4326"}
ROOT = Path(__file__).resolve().parents[3] / "datos" / "fuentes" / "snit-provincial-2026-11-15"
DATA = ROOT / "limiteprovincial_5k.geojson.gz"
META = ROOT / "metadatos.json"
PROVINCES = {"San José", "Alajuela", "Cartago", "Heredia", "Guanacaste", "Puntarenas", "Limón"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate(raw: bytes) -> dict:
    data = json.loads(raw.decode("utf-8"))
    if data.get("type") != "FeatureCollection" or data.get("numberMatched") != 7:
        raise ValueError("La respuesta no declara siete provincias")
    features = data.get("features", [])
    names = {f.get("properties", {}).get("PROVINCIA") for f in features}
    if len(features) != 7 or names != PROVINCES:
        raise ValueError("Las provincias están incompletas o duplicadas")
    if data.get("crs", {}).get("properties", {}).get("name") != "urn:ogc:def:crs:EPSG::4326":
        raise ValueError("El CRS reportado no es EPSG:4326")
    for feature in features:
        g = shape(feature["geometry"])
        if g.geom_type not in {"Polygon", "MultiPolygon"} or g.is_empty or not g.is_valid:
            raise ValueError("Geometría provincial inválida")
        west, south, east, north = g.bounds
        if not (-90 < west < east < -80 and 5 < south < north < 12):
            raise ValueError("Extensión geográfica inesperada")
    return {"feature_count": len(features), "provinces": sorted(names), "crs": "EPSG:4326"}


def capture() -> None:
    if DATA.exists() or META.exists():
        raise FileExistsError("La instantánea ya existe o está incompleta; no se sobrescribe")
    response = httpx.get(URL, params=PARAMS, follow_redirects=True, timeout=120)
    response.raise_for_status()
    raw = response.content
    summary = validate(raw)
    compressed = gzip.compress(raw, mtime=0)
    metadata = {
        "title": "División Territorial Administrativa de Costa Rica, límite provincial 1:5.000",
        "publisher": "Instituto Geográfico Nacional - Registro Nacional de Costa Rica / SNIT",
        "metadata_url": "https://meta2.snitcr.go.cr/geonetwork/srv/api/records/CR_IGN_LTA_DTA_5K_VE",
        "source_url": URL, "request_parameters": PARAMS,
        "accessed_at_utc": datetime.now(UTC).isoformat(),
        "declared_usage": "Uso libre y gratuito, con mención del origen y propiedad de los datos.",
        "sha256_geojson": digest(raw), "sha256_gzip": digest(compressed), "bytes_geojson": len(raw),
        **summary,
        "status": "fuente candidata; ámbito y geometría de análisis sin acordar",
    }
    ROOT.mkdir(parents=True, exist_ok=True)
    # exclusive creation avoids silently replacing a previous capture
    with DATA.open("xb") as file:
        file.write(compressed)
    with META.open("x", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"Capturada {DATA}; SHA-256 del GeoJSON: {metadata['sha256_geojson']}")


def verify() -> None:
    meta = json.loads(META.read_text(encoding="utf-8"))
    compressed = DATA.read_bytes()
    if digest(compressed) != meta["sha256_gzip"]:
        raise ValueError("La huella del archivo comprimido no coincide")
    raw = gzip.decompress(compressed)
    if digest(raw) != meta["sha256_geojson"] or len(raw) != meta["bytes_geojson"]:
        raise ValueError("La huella o tamaño del GeoJSON no coincide")
    if any(meta[key] != value for key, value in validate(raw).items()):
        raise ValueError("Los metadatos no corresponden a la captura")
    print(f"Captura íntegra: {meta['feature_count']} provincias, {meta['crs']}, SHA-256 {meta['sha256_geojson']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("capture", "verify"))
    args = parser.parse_args()
    capture() if args.action == "capture" else verify()
