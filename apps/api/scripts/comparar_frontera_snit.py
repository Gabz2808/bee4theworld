"""Compara la geometría provisional con la capa provincial IGN/SNIT, sin cambiar la API.

Ejecutar desde apps/api: .venv/Scripts/python.exe scripts/comparar_frontera_snit.py
El WFS es dinámico: la huella identifica la respuesta recibida, no una versión archivada.
"""
import hashlib
import argparse
import gzip
import json
import sys
from pathlib import Path

import httpx
from pyproj import Transformer
from shapely import transform
from shapely.geometry import shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.exploration_service import DEFAULT_COSTA_RICA_GEOM
from capturar_frontera_snit import DATA, verify

URL = "https://geos.snitcr.go.cr/be/IGN_5_CO/wfs"
PARAMS = {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "IGN_5_CO:limiteprovincial_5k", "outputFormat": "application/json", "srsName": "EPSG:4326"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true", help="Usar y verificar la captura local en vez del WFS en vivo")
    args = parser.parse_args()
    if args.snapshot:
        verify()
        raw = gzip.decompress(DATA.read_bytes())
    else:
        response = httpx.get(URL, params=PARAMS, follow_redirects=True, timeout=120)
        response.raise_for_status()
        raw = response.content
    data = json.loads(raw.decode("utf-8"))
    features = data["features"]
    if len(features) != 7 or data.get("numberMatched") != 7:
        raise ValueError("La capa no devolvió las siete provincias esperadas")
    geometries = [shape(feature["geometry"]) for feature in features]
    if any(g.is_empty or not g.is_valid for g in geometries):
        raise ValueError("La capa contiene geometrías vacías o inválidas")
    region = unary_union(geometries)
    if region.geom_type != "MultiPolygon" or not region.is_valid:
        raise ValueError("La unión no es el multipolígono válido esperado")
    projection = Transformer.from_crs(4326, 6933, always_xy=True).transform
    reference = transform(region, projection, interleaved=False)
    provisional = transform(shape(DEFAULT_COSTA_RICA_GEOM.model_dump()), projection, interleaved=False)
    overlap = reference.intersection(provisional).area
    parts = sorted((p.area for p in reference.geoms), reverse=True)
    vertices = sum(len(p.exterior.coords) + sum(len(r.coords) for r in p.interiors) for p in region.geoms)
    print(f"GeoJSON: {len(raw)} bytes; SHA-256 {hashlib.sha256(raw).hexdigest()}")
    print(f"Provincias: {len(features)}; CRS reportado: {data.get('crs')}; componentes: {len(parts)}; vértices: {vertices}")
    print(f"Área SNIT: {reference.area/1e6:.2f} km²; provisional: {provisional.area/1e6:.2f} km²; intersección: {overlap/1e6:.2f} km²")
    print(f"Provisional fuera de SNIT: {100*(1-overlap/provisional.area):.3f} %; SNIT fuera de provisional: {100*(1-overlap/reference.area):.3f} %")
    print(f"Mayor componente: {parts[0]/1e6:.2f} km²; demás componentes: {sum(parts[1:])/1e6:.2f} km²")
    print(f"Extensión: {region.bounds}. Los componentes no se clasifican automáticamente como continentales o insulares.")


if __name__ == "__main__":
    main()
