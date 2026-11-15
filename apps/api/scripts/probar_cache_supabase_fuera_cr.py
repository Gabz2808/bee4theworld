"""Script de verificación y pruebas fuera de Costa Rica con persistencia y caché en Supabase.

Ejecuta dos escenarios reales fuera de Costa Rica:
1. Región registrada en catálogo: Cuenca del Canal de Panamá (region_id).
2. Polígono personalizado en Colombia: Sabana de Bogotá (region GeoJSON).

Verifica:
- Ingesta o carga de datos satelitales NASA GPM IMERG V07.
- Registro y persistencia correcta en Supabase (public.regions, public.ingestion_runs, public.processed_data).
- Supabase Cache Hit al purgar la caché local en disco.
- Integridad científica e interpretación de resultados.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import date
from pathlib import Path

# Configurar path para importar app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from app.core.cache import get_cache_dir
from app.core.supabase_client import get_supabase_client
from app.models.exploration import ExplorationRequest
from app.models.geojson import GeoJSONPolygon
from app.services.exploration_service import run_exploration

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_supabase_fuera_cr")


def limpiar_cache_local() -> int:
    """Elimina los archivos de caché local en disco para forzar consulta a Supabase o NASA."""
    cache_dir = get_cache_dir()
    archivos = list(cache_dir.glob("*.json"))
    for f in archivos:
        f.unlink(missing_ok=True)
    return len(archivos)


def ejecutar_pruebas():
    print("=" * 70)
    print("🛰️  PRUEBAS DE EXPLORACIÓN FUERA DE COSTA RICA CON CACHÉ SUPABASE")
    print("=" * 70)

    sb = get_supabase_client()
    print("✅ Conexión establecida con Supabase.")

    # -------------------------------------------------------------------------
    # CASO 1: Región registrada en Panamá (Cuenca del Canal de Panamá)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("📍 CASO 1: Región registrada de catálogo: Cuenca del Canal de Panamá")
    print("   Identificador: 'cuenca-canal-panama' (2023-01-01 a 2023-12-31)")
    print("-" * 70)

    req_panama = ExplorationRequest(
        variable_id="precipitation",
        region_id="cuenca-canal-panama",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
    )

    t0 = time.perf_counter()
    resp_panama_1 = run_exploration(req_panama, supabase_client=sb)
    t1 = time.perf_counter()
    dur_1 = (t1 - t0) * 1000

    print(f"✅ Respuesta recibida en {dur_1:.1f} ms.")
    print(f"   Región resuelta: {resp_panama_1.metadata.selection.region_name} (ID: {resp_panama_1.metadata.selection.region_id})")
    print(f"   Meses procesados: {len(resp_panama_1.timeseries)}")
    print(f"   Tendencia calculada: {resp_panama_1.trend_analysis.status} (Método: {resp_panama_1.trend_analysis.method})")
    print(f"   Resumen analítico: {resp_panama_1.trend_analysis.summary}")
    print(f"   Interpretación: {resp_panama_1.interpretation.headline if resp_panama_1.interpretation else 'N/A'}")

    # Verificar en Supabase
    panama_reg = sb.table("regions").select("id, name").eq("name", "Cuenca del Canal de Panamá").execute().data
    assert len(panama_reg) == 1, "La región de Panamá debe estar en public.regions"
    panama_uuid = panama_reg[0]["id"]
    print(f"✅ Región verificada en public.regions con UUID: {panama_uuid}")

    runs_panama = (
        sb.table("ingestion_runs")
        .select("id, requested_start, requested_end, source_units, output_units")
        .eq("region_id", panama_uuid)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    assert len(runs_panama) >= 1, "Debe existir al menos un ingestion_run para Panamá en Supabase"
    run_id = runs_panama[0]["id"]
    print(f"✅ Ingestion run verificado en Supabase: {run_id} ({runs_panama[0]['requested_start']} a {runs_panama[0]['requested_end']})")

    data_panama = (
        sb.table("processed_data")
        .select("observed_month, precipitation_mm, coverage_fraction, quality_flag")
        .eq("ingestion_run_id", run_id)
        .order("observed_month")
        .execute()
        .data
    )
    assert len(data_panama) == 12, f"Deben haber 12 meses guardados en Supabase, se hallaron {len(data_panama)}"
    total_precip_sb = sum(r["precipitation_mm"] for r in data_panama)
    print(f"✅ 12 registros mensuales persistidos en public.processed_data. Precipitación acumulada: {total_precip_sb:.2f} mm")

    # TEST DE CACHÉ HIT EN SUPABASE:
    print("\n   ⚡ Probando Supabase Cache Hit para Panamá:")
    num_purgados = limpiar_cache_local()
    print(f"   - Caché local purgada ({num_purgados} archivos eliminados).")

    t_cache_0 = time.perf_counter()
    resp_panama_cache = run_exploration(req_panama, supabase_client=sb)
    t_cache_1 = time.perf_counter()
    dur_cache = (t_cache_1 - t_cache_0) * 1000

    print(f"   - Tiempo de respuesta desde Supabase Cache: {dur_cache:.1f} ms")
    assert dur_cache < 2500, "La respuesta desde Supabase cache debe ser rápida (< 2.5s)"
    assert len(resp_panama_cache.timeseries) == 12, "Debe retornar los 12 meses exactos"
    assert resp_panama_cache.timeseries[0].value == resp_panama_1.timeseries[0].value
    print("   🎉 Supabase Cache Hit comprobado con éxito para Cuenca del Canal de Panamá!")

    # -------------------------------------------------------------------------
    # CASO 2: Polígono personalizado en Colombia (Sabana de Bogotá)
    # -------------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("📍 CASO 2: Polígono personalizado fuera de Costa Rica: Sabana de Bogotá (Colombia)")
    print("   Coordenadas: [[-74.25, 4.5], [-74.0, 4.5], [-74.0, 4.85], [-74.25, 4.85], [-74.25, 4.5]]")
    print("   Período: 2023-01-01 a 2023-12-31")
    print("-" * 70)

    bogota_geom = GeoJSONPolygon(
        type="Polygon",
        coordinates=[
            [
                [-74.25, 4.50],
                [-74.00, 4.50],
                [-74.00, 4.85],
                [-74.25, 4.85],
                [-74.25, 4.50],
            ]
        ],
    )

    req_bogota = ExplorationRequest(
        variable_id="precipitation",
        region=bogota_geom,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
    )

    t0_b = time.perf_counter()
    resp_bogota_1 = run_exploration(req_bogota, supabase_client=sb)
    t1_b = time.perf_counter()
    dur_b1 = (t1_b - t0_b) * 1000

    print(f"✅ Respuesta recibida en {dur_b1:.1f} ms.")
    print(f"   Región resuelta: {resp_bogota_1.metadata.selection.region_name} (ID: {resp_bogota_1.metadata.selection.region_id})")
    print(f"   Meses procesados: {len(resp_bogota_1.timeseries)}")
    print(f"   Tendencia calculada: {resp_bogota_1.trend_analysis.status} (Método: {resp_bogota_1.trend_analysis.method})")
    print(f"   Resumen analítico: {resp_bogota_1.trend_analysis.summary}")
    print(f"   Interpretación: {resp_bogota_1.interpretation.headline if resp_bogota_1.interpretation else 'N/A'}")

    # Verificar que el polígono personalizado se registró dinámicamente en Supabase
    bogota_reg = (
        sb.table("regions")
        .select("id, name, geom")
        .ilike("name", "Polígono Personalizado%")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    assert len(bogota_reg) >= 1, "El polígono personalizado debe estar registrado en public.regions"
    bogota_uuid = bogota_reg[0]["id"]
    print(f"✅ Polígono personalizado registrado dinámicamente en public.regions: {bogota_reg[0]['name']} (UUID: {bogota_uuid})")

    runs_bogota = (
        sb.table("ingestion_runs")
        .select("id, requested_start, requested_end")
        .eq("region_id", bogota_uuid)
        .order("created_at", desc=True)
        .execute()
        .data
    )
    assert len(runs_bogota) >= 1, "Debe existir un ingestion_run para Bogotá en Supabase"
    run_id_bogota = runs_bogota[0]["id"]
    print(f"✅ Ingestion run de Bogotá verificado en Supabase: {run_id_bogota}")

    data_bogota = (
        sb.table("processed_data")
        .select("observed_month, precipitation_mm, coverage_fraction, quality_flag")
        .eq("ingestion_run_id", run_id_bogota)
        .order("observed_month")
        .execute()
        .data
    )
    assert len(data_bogota) == 12, f"Deben haber 12 meses guardados en Supabase, se hallaron {len(data_bogota)}"
    total_precip_bogota = sum(r["precipitation_mm"] for r in data_bogota)
    print(f"✅ 12 registros de Bogotá persistidos en public.processed_data. Acumulado: {total_precip_bogota:.2f} mm")

    # TEST DE CACHÉ HIT EN SUPABASE PARA POLÍGONO PERSONALIZADO:
    print("\n   ⚡ Probando Supabase Cache Hit para Polígono Personalizado (Bogotá):")
    limpiar_cache_local()
    print("   - Caché local purgada.")

    t_cache_b0 = time.perf_counter()
    resp_bogota_cache = run_exploration(req_bogota, supabase_client=sb)
    t_cache_b1 = time.perf_counter()
    dur_cache_b = (t_cache_b1 - t_cache_b0) * 1000

    print(f"   - Tiempo de respuesta desde Supabase Cache: {dur_cache_b:.1f} ms")
    assert dur_cache_b < 2500, "La respuesta desde Supabase cache debe ser rápida (< 2.5s)"
    assert len(resp_bogota_cache.timeseries) == 12
    assert resp_bogota_cache.timeseries[0].value == resp_bogota_1.timeseries[0].value
    print("   🎉 Supabase Cache Hit comprobado con éxito para Polígono Personalizado en Colombia!")

    print("\n" + "=" * 70)
    print("🌟 TODAS LAS PRUEBAS FUERA DE COSTA RICA Y CACHÉ SUPABASE PASARON SATISFACTORIAMENTE")
    print("=" * 70)


if __name__ == "__main__":
    ejecutar_pruebas()
