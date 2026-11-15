"""Comprobación de catálogo CMR y comparación orientativa de geometrías, sin escritura remota."""
from __future__ import annotations

import collections
import sys
from pathlib import Path

import httpx
from pyproj import Transformer
from shapely import transform
from shapely.geometry import shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.exploration_service import DEFAULT_COSTA_RICA_GEOM

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
BOUNDARY = "https://www.geoboundaries.org/api/current/gbOpen/CRI/ADM0/"
PINNED_GEOJSON = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/CRI/ADM0/geoBoundaries-CRI-ADM0.geojson"


def main() -> None:
    with httpx.Client(timeout=90, follow_redirects=True) as client:
        response = client.get(CMR, params={"short_name": "GPM_3IMERGM", "version": "07", "temporal": "2001-01-01T00:00:00Z,2024-12-31T23:59:59Z", "page_size": 2000})
        response.raise_for_status()
        entries = response.json()["feed"]["entry"]
        counts = collections.Counter(entry["time_start"][:7] for entry in entries)
        months = [f"{year:04d}-{month:02d}" for year in range(2001, 2025) for month in range(1, 13)]
        print("CMR: gránulos", len(entries), "meses únicos", len(counts))
        print("Meses faltantes:", [month for month in months if counts[month] == 0])
        print("Meses duplicados:", [(month, counts[month]) for month in months if counts[month] > 1])
        print("Colecciones:", sorted({entry["collection_concept_id"] for entry in entries}))

        metadata = client.get(BOUNDARY)
        metadata.raise_for_status()
        print("Metadatos actuales de geoBoundaries (pueden cambiar independientemente de la geometría fijada):")
        for key in ("boundaryID", "boundaryYearRepresented", "boundarySource", "boundaryLicense", "buildDate"):
            print(key, metadata.json().get(key))
        response = client.get(PINNED_GEOJSON)
        response.raise_for_status()
        reference = unary_union([shape(feature["geometry"]) for feature in response.json()["features"]])
        region = shape(DEFAULT_COSTA_RICA_GEOM.model_dump())
        project = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True).transform
        region = transform(region, project, interleaved=False)
        reference = transform(reference, project, interleaved=False)
        overlap = reference.intersection(region).area
        print(f"Área de referencia: {reference.area / 1e6:.1f} km²; polígono: {region.area / 1e6:.1f} km²")
        print(f"Intersección: {overlap / 1e6:.1f} km²; fracción de referencia: {overlap / reference.area:.4f}; fracción de polígono: {overlap / region.area:.4f}")
        print("La referencia es orientativa, no una frontera oficial ni validación de la serie.")


if __name__ == "__main__":
    main()
