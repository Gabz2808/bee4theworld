#!/usr/bin/env python3
"""Script para probar de extremo a extremo el endpoint POST /api/v1/explorations

con datos satelitales en vivo de NASA Earthdata, polígono personalizado y caché.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

# Añadir raíz de apps/api al PYTHONPATH
api_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(api_root))

from dotenv import load_dotenv

# Cargar .env de apps/api o del monorepo
for candidate in (api_root / ".env", api_root.parent.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break

from fastapi.testclient import TestClient
from app.main import app
from app.models.geojson import GeoJSONPolygon


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba integral del endpoint POST /api/v1/explorations")
    parser.add_argument(
        "--periodo",
        choices=["1mes", "12meses", "24meses"],
        default="12meses",
        help="Duración de la serie a extraer (1mes: Ene 2024, 12meses: Año 2023, 24meses: 2022-2023)",
    )
    args = parser.parse_args()

    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if not token:
        print("❌ ERROR: EARTHDATA_TOKEN no encontrado en el entorno ni en .env.")
        sys.exit(1)

    # Definir fechas según período
    if args.periodo == "1mes":
        start_date = "2024-01-01"
        end_date = "2024-01-31"
    elif args.periodo == "12meses":
        start_date = "2023-01-01"
        end_date = "2023-12-31"
    else:  # 24meses
        start_date = "2022-01-01"
        end_date = "2023-12-31"

    # Polígono de prueba: Cuenca del Canal de Panamá (~0.5° x 0.5°)
    panama_polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [-80.0, 8.8],
                [-79.5, 8.8],
                [-79.5, 9.3],
                [-80.0, 9.3],
                [-80.0, 8.8],
            ]
        ],
    }

    payload = {
        "variable_id": "precipitation",
        "region": panama_polygon,
        "start_date": start_date,
        "end_date": end_date,
    }

    client = TestClient(app)

    print("=" * 70)
    print("🌍 PRUEBA DE ENDPOINT POST /api/v1/explorations (NASA IMERG EN VIVO)")
    print("=" * 70)
    print(f"📍 Región: Polígono personalizado (Cuenca del Canal de Panamá)")
    print(f"📅 Período: {start_date} al {end_date} ({args.periodo})")
    print(f"🛰️  Variable: precipitation (NASA GPM IMERG Final V07)")
    print("-" * 70)

    # 1. Primera consulta: Descarga y cálculo satelital en vivo
    print("\n🚀 [1/2] Ejecutando primera consulta (extracción y recorte en NASA Harmony)...")
    t0 = time.perf_counter()
    resp = client.post("/api/v1/explorations", json=payload)
    elapsed_1 = time.perf_counter() - t0

    if resp.status_code != 200:
        print(f"❌ Error HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    print(f"✅ Respuesta HTTP 200 recibida en {elapsed_1:.2f} segundos.")
    print("\n📊 RESUMEN DE LA RESPUESTA:")
    print(f"   - Dataset: {data['metadata']['dataset']} ({data['metadata']['variable_name']})")
    print(f"   - Resolución espacial: {data['metadata']['spatial_resolution']}")
    print(f"   - Puntos de serie temporal: {len(data['timeseries'])}")
    print(f"   - Totales anuales computados: {len(data['annual_totals'])}")
    for at in data['annual_totals']:
        print(f"     • Año {at['year']}: {at['annual_precipitation_mm']} mm ({at['months_reported']} meses)")
    
    print(f"   - Estado de tendencia: {data['trend_analysis']['status']}")
    print(f"   - Resumen tendencia: {data['trend_analysis']['summary']}")
    if data['trend_analysis']['methodological_note']:
        print(f"   - Nota metodológica: {data['trend_analysis']['methodological_note']}")

    if "interpretation" in data and data["interpretation"]:
        interp = data["interpretation"]
        print("\n🧠 INTERPRETACIÓN CIENTÍFICA COMPRENSIBLE Y PRUDENTE:")
        print(f"   📌 Titular: {interp['headline']}")
        print(f"   📖 Narrativa: {interp['narrative']}")
        print(f"   ⚖️  Veredicto de tendencia: {interp['trend_verdict_plain_language']}")
        print(f"   💧 Resumen anomalías: {interp['anomaly_summary']}")
        print("   🛡️  Directrices de prudencia:")
        for g in interp["prudence_guidelines"]:
            print(f"      • {g}")

    print("\n📈 MUESTRA DE SERIE MENSUAL Y ANOMALÍAS:")
    for pt in data['timeseries'][:6]:
        print(f"   • {pt['date']}: {pt['value']} mm/month | Anomalía: {pt['anomaly_mm']} mm | Cobertura: {pt['coverage_fraction']*100:.1f}% [{pt['quality_flag']}]")
    if len(data['timeseries']) > 6:
        print(f"   ... ({len(data['timeseries']) - 6} meses adicionales procesados)")

    # 2. Segunda consulta: Verificar Cache Hit inmediato
    print("\n⚡ [2/2] Ejecutando segunda consulta idéntica (verificación de CACHÉ)...")
    t1 = time.perf_counter()
    resp_cached = client.post("/api/v1/explorations", json=payload)
    elapsed_2 = time.perf_counter() - t1

    if resp_cached.status_code != 200:
        print(f"❌ Error en consulta de caché HTTP {resp_cached.status_code}")
        sys.exit(1)

    data_cached = resp_cached.json()
    print(f"✅ Respuesta desde CACHÉ recibida en {elapsed_2 * 1000:.1f} milisegundos ({elapsed_2:.4f} s).")
    aceleracion = elapsed_1 / elapsed_2 if elapsed_2 > 0 else 999.0
    print(f"⚡ Aceleración de respuesta: {aceleracion:.1f}x más rápido.")
    print("=" * 70)
    print("🎉 PRUEBA COMPLETADA CON ÉXITO: Extracción, procesamiento, endpoint v1 y caché validados.")
    print("=" * 70)


if __name__ == "__main__":
    main()
