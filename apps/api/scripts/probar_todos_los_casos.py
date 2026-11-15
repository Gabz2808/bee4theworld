#!/usr/bin/env python3
"""Script de pruebas exhaustivas para todos los endpoints y casos de uso de Iyök API.

Ejecuta casos exitosos (200 OK), casos de error controlado (400, 404, 422) y rutas heredadas,
validando la integridad de contratos, respuestas, interpretación científica y tiempos de respuesta.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Añadir raíz de apps/api al PYTHONPATH
api_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(api_root))

from dotenv import load_dotenv

for candidate in (api_root / ".env", api_root.parent.parent / ".env"):
    if candidate.exists():
        load_dotenv(candidate)
        break

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Contador de resultados
passed_count = 0
failed_count = 0
total_cases = 0


def log_case(case_num: str, title: str, method: str, path: str, expected_code: int, actual_code: int, success: bool, note: str = "") -> None:
    global passed_count, failed_count, total_cases
    total_cases += 1
    if success:
        passed_count += 1
        icon = "✅ PASS"
    else:
        failed_count += 1
        icon = "❌ FAIL"

    status_str = f"HTTP {actual_code} (Esperado: {expected_code})"
    print(f"{icon} [{case_num}] {title}")
    print(f"      {method} {path} -> {status_str}")
    if note:
        print(f"      ℹ️  {note}")
    print()


def main() -> None:
    print("=" * 75)
    print("🧪 SUITE INTEGRAL DE PRUEBAS PARA TODOS LOS ENDPOINTS Y CASOS DE USO")
    print("=" * 75)
    print()

    # =========================================================================
    # BLOQUE 1: HEALTH CHECK Y CATÁLOGO
    # =========================================================================
    print("📂 BLOQUE 1: Health Check y Catálogo Oficial")
    print("-" * 75)

    # Caso 1.1: GET /ping
    resp = client.get("/ping")
    ok = resp.status_code == 200 and resp.json().get("status") == "ok"
    log_case("1.1", "Health check del servicio", "GET", "/ping", 200, resp.status_code, ok, "Responde {'status': 'ok'}")

    # Caso 1.2: GET /api/v1/catalog
    resp = client.get("/api/v1/catalog")
    data = resp.json() if resp.status_code == 200 else {}
    has_regions = len(data.get("regions", [])) >= 1
    has_vars = len(data.get("variables", [])) >= 1
    has_combs = len(data.get("combinations", [])) >= 1
    ok = resp.status_code == 200 and has_regions and has_vars and has_combs
    log_case(
        "1.2",
        "Catálogo unificado de opciones",
        "GET",
        "/api/v1/catalog",
        200,
        resp.status_code,
        ok,
        f"Regiones: {len(data.get('regions', []))}, Variables: {len(data.get('variables', []))}, Combinaciones: {len(data.get('combinations', []))}",
    )

    # =========================================================================
    # BLOQUE 2: RUTAS OBSOLETAS (HEREDADAS)
    # =========================================================================
    print("📂 BLOQUE 2: Rechazo de Rutas Heredadas / Obsoletas (404)")
    print("-" * 75)

    # Caso 2.1: GET /api/regions (debe fallar 404)
    resp = client.get("/api/regions")
    ok = resp.status_code == 404
    log_case("2.1", "Ruta obsoleta /api/regions", "GET", "/api/regions", 404, resp.status_code, ok, "No expone endpoints no versionados")

    # Caso 2.2: GET /api/variables (debe fallar 404)
    resp = client.get("/api/variables")
    ok = resp.status_code == 404
    log_case("2.2", "Ruta obsoleta /api/variables", "GET", "/api/variables", 404, resp.status_code, ok, "No expone endpoints no versionados")

    # Caso 2.3: POST /api/exploration (debe fallar 404)
    resp = client.post("/api/exploration", json={})
    ok = resp.status_code == 404
    log_case("2.3", "Ruta obsoleta /api/exploration", "POST", "/api/exploration", 404, resp.status_code, ok, "No expone endpoints no versionados")

    # =========================================================================
    # BLOQUE 3: CASOS EXITOSOS DE EXPLORACIÓN (HTTP 200)
    # =========================================================================
    print("📂 BLOQUE 3: Consultas de Exploración Válidas (HTTP 200)")
    print("-" * 75)

    # Caso 3.1: Costa Rica Continental por region_id (1 año: 2023)
    p_cr = {
        "region_id": "costa-rica-continental",
        "variable_id": "precipitation",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }
    t0 = time.perf_counter()
    resp = client.post("/api/v1/explorations", json=p_cr)
    t_cr = time.perf_counter() - t0
    data = resp.json() if resp.status_code == 200 else {}
    has_series = len(data.get("timeseries", [])) == 12
    has_annual = len(data.get("annual_totals", [])) == 1
    has_interp = bool(data.get("interpretation"))
    ok = resp.status_code == 200 and has_series and has_annual and has_interp
    annual_mm = data.get("annual_totals", [{}])[0].get("annual_precipitation_mm", 0)
    log_case(
        "3.1",
        "Exploración por region_id (Costa Rica 2023)",
        "POST",
        "/api/v1/explorations",
        200,
        resp.status_code,
        ok,
        f"Tiempo: {t_cr:.2f}s | 12 meses | Total anual: {annual_mm} mm | Interpretación generada",
    )

    # Caso 3.2: Polígono Personalizado (Panamá 2023) - Desde Caché / Live
    panama_geom = {
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
    p_panama = {
        "region": panama_geom,
        "variable_id": "precipitation",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }
    t0 = time.perf_counter()
    resp = client.post("/api/v1/explorations", json=p_panama)
    t_panama = time.perf_counter() - t0
    data = resp.json() if resp.status_code == 200 else {}
    ok = resp.status_code == 200 and len(data.get("timeseries", [])) == 12 and bool(data.get("interpretation"))
    log_case(
        "3.2",
        "Polígono personalizado (Cuenca Canal Panamá 2023)",
        "POST",
        "/api/v1/explorations",
        200,
        resp.status_code,
        ok,
        f"Tiempo: {t_panama:.3f}s | Titular: {data.get('interpretation', {}).get('headline', '')[:50]}...",
    )

    # Caso 3.3: Cache Hit Ultrarrápido (Re-consulta inmediata de Panamá)
    t0 = time.perf_counter()
    resp_cache = client.post("/api/v1/explorations", json=p_panama)
    t_cache = time.perf_counter() - t0
    ok = resp_cache.status_code == 200 and t_cache < 0.2
    log_case(
        "3.3",
        "Comprobación de Caché (Cache Hit Inmediato)",
        "POST",
        "/api/v1/explorations",
        200,
        resp_cache.status_code,
        ok,
        f"Tiempo: {t_cache*1000:.1f} ms (< 200 ms) | Aceleración verificada",
    )

    # Caso 3.4: Uso de objeto alternativo 'date_range' en lugar de start_date/end_date
    p_drange = {
        "region_id": "costa-rica-continental",
        "variable_id": "precipitation",
        "date_range": {
            "start": "2023-01-01",
            "end": "2023-12-31",
        },
    }
    resp = client.post("/api/v1/explorations", json=p_drange)
    ok = resp.status_code == 200 and len(resp.json().get("timeseries", [])) == 12
    log_case(
        "3.4",
        "Formato alternativo de fechas con 'date_range'",
        "POST",
        "/api/v1/explorations",
        200,
        resp.status_code,
        ok,
        "Normaliza automáticamente date_range a start_date y end_date",
    )

    # Caso 3.5: Período corto de 1 mes (Enero 2024) -> not_computed en tendencia
    p_1mes = {
        "region": panama_geom,
        "variable_id": "precipitation",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
    }
    resp = client.post("/api/v1/explorations", json=p_1mes)
    data = resp.json() if resp.status_code == 200 else {}
    trend_status = data.get("trend_analysis", {}).get("status")
    ok = resp.status_code == 200 and trend_status == "not_computed"
    log_case(
        "3.5",
        "Período de 1 mes (sin años completos cerrados)",
        "POST",
        "/api/v1/explorations",
        200,
        resp.status_code,
        ok,
        f"trend_analysis.status == '{trend_status}' (Rigor metodológico respetado)",
    )

    # =========================================================================
    # BLOQUE 4: VALIDACIONES Y RECHAZOS CIENTÍFICOS (400, 404, 422)
    # =========================================================================
    print("📂 BLOQUE 4: Validaciones y Rechazos Científicos de Entrada")
    print("-" * 75)

    # Caso 4.1: Error 404 - Region inexistente en catálogo
    p_bad_reg = {
        "region_id": "territorio-desconocido-999",
        "variable_id": "precipitation",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }
    resp = client.post("/api/v1/explorations", json=p_bad_reg)
    err = resp.json().get("error", {})
    ok = resp.status_code == 404 and err.get("code") == "NOT_FOUND"
    log_case(
        "4.1",
        "Región inexistente en catálogo (404)",
        "POST",
        "/api/v1/explorations",
        404,
        resp.status_code,
        ok,
        f"Error code: '{err.get('code')}' | Mensaje: {err.get('message', '')}",
    )

    # Caso 4.2: Error 400 - Fecha de inicio no alineada a inicio de mes (ej. día 15)
    p_bad_start = {
        "region_id": "costa-rica-continental",
        "variable_id": "precipitation",
        "start_date": "2023-01-15",
        "end_date": "2023-12-31",
    }
    resp = client.post("/api/v1/explorations", json=p_bad_start)
    err = resp.json().get("error", {})
    ok = resp.status_code == 400 and err.get("code") == "INVALID_REQUEST" and "primer día" in err.get("message", "")
    log_case(
        "4.2",
        "Fecha inicio desalineada de mes (400)",
        "POST",
        "/api/v1/explorations",
        400,
        resp.status_code,
        ok,
        f"Exige día 1 del mes para preservar la agregación mensual IMERG",
    )

    # Caso 4.3: Error 400 - Fecha final no alineada a último día de mes (ej. día 20)
    p_bad_end = {
        "region_id": "costa-rica-continental",
        "variable_id": "precipitation",
        "start_date": "2023-01-01",
        "end_date": "2023-01-20",
    }
    resp = client.post("/api/v1/explorations", json=p_bad_end)
    err = resp.json().get("error", {})
    ok = resp.status_code == 400 and err.get("code") == "INVALID_REQUEST" and "último día" in err.get("message", "")
    log_case(
        "4.3",
        "Fecha final desalineada de mes (400)",
        "POST",
        "/api/v1/explorations",
        400,
        resp.status_code,
        ok,
        f"Exige último día de mes para evitar meses truncados",
    )

    # Caso 4.4: Error 400 - Fecha final anterior a la inicial
    p_inverted_dates = {
        "region_id": "costa-rica-continental",
        "variable_id": "precipitation",
        "start_date": "2023-12-01",
        "end_date": "2023-01-31",
    }
    resp = client.post("/api/v1/explorations", json=p_inverted_dates)
    err = resp.json().get("error", {})
    ok = resp.status_code in (400, 422)
    log_case(
        "4.4",
        "Rango de fechas invertido (start > end)",
        "POST",
        "/api/v1/explorations",
        400,
        resp.status_code,
        ok,
        f"Rechazado con {resp.status_code}: {err.get('message', '')}",
    )

    # Caso 4.5: Error 400 - Fechas fuera de rango de cobertura de IMERG V07 (ej. año 1999)
    p_out_range = {
        "region_id": "costa-rica-continental",
        "variable_id": "precipitation",
        "start_date": "1999-01-01",
        "end_date": "1999-12-31",
    }
    resp = client.post("/api/v1/explorations", json=p_out_range)
    err = resp.json().get("error", {})
    ok = resp.status_code == 400 and err.get("code") == "INVALID_REQUEST" and "fuera del intervalo disponible" in err.get("message", "")
    log_case(
        "4.5",
        "Fechas fuera de cobertura IMERG V07 (400)",
        "POST",
        "/api/v1/explorations",
        400,
        resp.status_code,
        ok,
        "Protege contra consultas previas a la misión satelital (2001)",
    )

    # Caso 4.6: Error 422 - Variable no permitida en MVP (ej. temperatura_superficial)
    p_bad_var = {
        "region_id": "costa-rica-continental",
        "variable_id": "temperatura_superficial",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }
    resp = client.post("/api/v1/explorations", json=p_bad_var)
    err = resp.json().get("error", {})
    ok = resp.status_code == 422 and err.get("code") == "VALIDATION_ERROR"
    log_case(
        "4.6",
        "Variable no soportada en el MVP (422)",
        "POST",
        "/api/v1/explorations",
        422,
        resp.status_code,
        ok,
        "Solo permite 'precipitation' bajo el contrato oficial de lanzamiento",
    )

    # Caso 4.7: Error 422 - Polígono GeoJSON no cerrado (primer y último punto difieren)
    p_unclosed = {
        "region": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-80.0, 8.8],
                    [-79.5, 8.8],
                    [-79.5, 9.3],
                    [-80.0, 9.3],  # Falta el cierre a [-80.0, 8.8]
                ]
            ],
        },
        "variable_id": "precipitation",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }
    resp = client.post("/api/v1/explorations", json=p_unclosed)
    err = resp.json().get("error", {})
    ok = resp.status_code == 422 and err.get("code") == "VALIDATION_ERROR"
    log_case(
        "4.7",
        "Polígono GeoJSON abierto / no cerrado (422)",
        "POST",
        "/api/v1/explorations",
        422,
        resp.status_code,
        ok,
        "Valida la especificación formal OGC/RFC 7946 de polígonos GeoJSON",
    )

    # Caso 4.8: Error 400/422 - Petición sin region_id ni region
    p_missing_reg = {
        "variable_id": "precipitation",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
    }
    resp = client.post("/api/v1/explorations", json=p_missing_reg)
    err = resp.json().get("error", {})
    ok = resp.status_code in (400, 422)
    log_case(
        "4.8",
        "Petición huérfana sin región ni polígono (422/400)",
        "POST",
        "/api/v1/explorations",
        422,
        resp.status_code,
        ok,
        "Exige obligatoriamente definir el ámbito espacial",
    )

    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================
    print("=" * 75)
    print(f"📊 RESUMEN FINAL DE LA EVALUACIÓN: {passed_count}/{total_cases} CASOS SUPERADOS CON ÉXITO")
    print("=" * 75)
    if failed_count == 0:
        print("🎉 ¡TODOS LOS ENDPOINTS Y CASOS DE USO PASARON AL 100%!")
        print("   - Health check y Catálogo v1: Operativos.")
        print("   - Rutas obsoletas: Bloqueadas con 404.")
        print("   - Ingesta satelital, agregación y caché: 100% validadas.")
        print("   - Interpretación científica y directrices de prudencia: Activas.")
        print("   - Rechazos por integridad científica (fechas, polígonos, variables): 100% blindados.")
    else:
        print(f"⚠️  Hubo {failed_count} fallos que requieren revisión.")


if __name__ == "__main__":
    main()
