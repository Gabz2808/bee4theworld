#!/usr/bin/env python3
"""Script de diagnóstico y extracción en vivo con NASA Earthdata / Harmony.

Verifica la validez de EARTHDATA_TOKEN y demuestra la extracción satelital
en tiempo real para cualquier región geográfica de América Latina.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# Añadir raíz de apps/api al PYTHONPATH
api_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(api_root))

from dotenv import load_dotenv

# Cargar .env de apps/api o del monorepo
env_path = api_root / ".env"
if not env_path.exists():
    env_path = api_root.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

import httpx
from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import GPMIMERGConnector
from harmony import Client


def verificar_credenciales() -> str:
    print("=" * 60)
    print("🛰️  VERIFICACIÓN DE CREDENCIALES NASA EARTHDATA")
    print("=" * 60)

    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not token:
        print("❌ ERROR: No se encontró la variable EARTHDATA_TOKEN en el entorno ni en .env.")
        print("ℹ️  Por favor, añade tu token a apps/api/.env:")
        print("   EARTHDATA_TOKEN=tu_token_aqui")
        sys.exit(1)

    masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
    print(f"✅ Token detectado en el entorno: {masked_token} (Longitud: {len(token)} caracteres)")
    return token


def verificar_cmr() -> None:
    print("\n🔍 1. Comprobando catálogo de NASA CMR...")
    cmr_url = "https://cmr.earthdata.nasa.gov/search/granules.json"
    params = {
        "short_name": "GPM_3IMERGM",
        "version": "07",
        "page_size": 1,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(cmr_url, params=params)
            resp.raise_for_status()
            feed = resp.json().get("feed", {})
            total_hits = resp.headers.get("CMR-Hits", len(feed.get("entry", [])))
            print(f"✅ Conexión exitosa a NASA CMR. Granules totales encontrados en CMR: {total_hits}")
    except Exception as e:  # noqa: BLE001 - boundary fallback
        print(f"❌ Error al consultar NASA CMR: {e}")
        sys.exit(1)


def verificar_harmony(token: str) -> Client:
    print("\n🔗 2. Inicializando cliente NASA Harmony con autenticación...")
    try:
        client = Client(token=token)
        print("✅ Cliente Harmony inicializado correctamente.")
        return client
    except Exception as e:  # noqa: BLE001 - boundary fallback
        print(f"❌ Error inicializando cliente Harmony: {e}")
        sys.exit(1)


def prueba_extraccion_region(nombre: str, geom: GeoJSONPolygon, start: date, end: date) -> None:
    print(f"\n🌎 3. Prueba de extracción satelital en vivo para: {nombre}")
    print(f"   Período solicitado: {start} a {end}")
    print("   Enviando solicitud de recorte espacial y descarga a NASA Harmony...")

    connector = GPMIMERGConnector()
    try:
        resultado = connector.fetch_monthly_precipitation(geom, start, end)
        print("✅ ¡Extracción exitosa!")
        print(f"   Dataset: {resultado.dataset}")
        print(f"   Unidades obtenidas: {resultado.source_units}")
        print(f"   Meses procesados: {len(resultado.monthly_values)}")
        for val in resultado.monthly_values:
            print(f"   - Mes {val.month:%Y-%m}: {val.value:.2f} mm/hr (Cobertura territorial: {val.coverage_fraction*100:.1f}%)")
    except Exception as e:  # noqa: BLE001 - boundary fallback
        print(f"❌ Error durante la extracción de datos satelitales: {e}")


def main() -> None:
    token = verificar_credenciales()
    verificar_cmr()
    verificar_harmony(token)

    # Ejemplo: Pequeño polígono de prueba en la Cuenca del Canal de Panamá
    # Bounding box ~ 0.5° x 0.5° para una descarga rápida de prueba
    panama_test_geom = GeoJSONPolygon(
        type="Polygon",
        coordinates=[
            [
                [-80.0, 8.8],
                [-79.5, 8.8],
                [-79.5, 9.3],
                [-80.0, 9.3],
                [-80.0, 8.8],
            ]
        ],
    )

    print("\n💡 Diagnóstico completado. Si deseas ejecutar una descarga de prueba de 1 mes (ej. Enero 2024),")
    print("   puedes invocar este script con el argumento '--descargar-prueba':")
    print("   python apps/api/scripts/verificar_earthdata.py --descargar-prueba")

    if "--descargar-prueba" in sys.argv:
        prueba_extraccion_region(
            "Cuenca Canal de Panamá (Prueba 1 mes)",
            panama_test_geom,
            date(2024, 1, 1),
            date(2024, 1, 31),
        )


if __name__ == "__main__":
    main()
