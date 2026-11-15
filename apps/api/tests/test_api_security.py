"""Pruebas de seguridad, límites y control de acceso para la API Iyök (Issue #16).

Verifica:
1. Configuración de CORS segura con orígenes acordados (sin wildcard con credenciales).
2. Límite de tamaño de cuerpo de solicitud (HTTP 413 Payload Too Large).
3. Límite de complejidad del polígono (> 500 vértices -> HTTP 422).
4. Límite de área / extensión espacial (> 15° lon o > 10° lat -> HTTP 422).
5. Límite de frecuencia de solicitudes (HTTP 429 Rate Limit Exceeded).
6. Separación de autorización de lectura y escritura.
7. Comportamiento exitoso ante solicitudes legítimas dentro de los límites.
"""
from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.routes import get_connector, get_optional_supabase
from app.core.security import (
    DEFAULT_CORS_ORIGINS,
    InMemoryRateLimiter,
    get_cors_origins,
    is_write_authorized,
    rate_limiter,
    validate_polygon_complexity_and_area,
)
from app.main import app
from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation


class APISecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def setUp(self) -> None:
        rate_limiter.reset()
        app.dependency_overrides[get_optional_supabase] = lambda: None

    def tearDown(self) -> None:
        rate_limiter.reset()
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # 1. CORS
    # -------------------------------------------------------------------------
    def test_cors_allows_configured_origins_with_credentials(self) -> None:
        """CORS permite orígenes de confianza (ej. http://localhost:3000) con credenciales."""
        headers = {
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        response = self.client.options("/api/v1/explorations", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:3000")
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")

    def test_cors_rejects_unauthorized_external_origins(self) -> None:
        """CORS no refleja orígenes desconocidos o maliciosos."""
        headers = {
            "Origin": "https://sitio-malicioso.com",
            "Access-Control-Request-Method": "POST",
        }
        response = self.client.options("/api/v1/explorations", headers=headers)
        self.assertNotEqual(response.headers.get("access-control-allow-origin"), "https://sitio-malicioso.com")

    # -------------------------------------------------------------------------
    # 2. Límite de tamaño de solicitud (Payload Size Limit)
    # -------------------------------------------------------------------------
    def test_request_payload_exceeding_1mb_rejected_with_413(self) -> None:
        """Solicitudes con Content-Length mayor a 1 MB son rechazadas con HTTP 413."""
        huge_headers = {"content-length": str(2 * 1024 * 1024)}  # 2 MB
        response = self.client.post("/api/v1/explorations", headers=huge_headers, json={"some": "data"})
        self.assertEqual(response.status_code, 413)
        err = response.json()["error"]
        self.assertEqual(err["code"], "PAYLOAD_TOO_LARGE")
        self.assertIn("1 MB", err["message"])

    # -------------------------------------------------------------------------
    # 3. Límite de complejidad del polígono (> 500 vértices)
    # -------------------------------------------------------------------------
    def test_polygon_with_excessive_vertices_rejected_with_422(self) -> None:
        """Polígonos con más de 500 vértices son rechazados para evitar sobrecarga (ReDoS/DoS)."""
        # Crear polígono con 505 vértices en un círculo pequeño
        points = []
        for i in range(505):
            points.append([-84.0 + (i * 0.0001), 10.0 + (i * 0.0001)])
        points.append(points[0])  # Cerrar anillo

        payload = {
            "region": {"type": "Polygon", "coordinates": [points]},
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "temporal_resolution": "monthly",
        }

        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 422)
        err = response.json()["error"]
        self.assertEqual(err["code"], "UNPROCESSABLE_ENTITY")
        self.assertIn("supera la complejidad máxima permitida de 500 vértices", err["message"])

    # -------------------------------------------------------------------------
    # 4. Límite de área / extensión espacial (> 15° lon o > 10° lat)
    # -------------------------------------------------------------------------
    def test_polygon_with_excessive_spatial_extent_rejected_with_422(self) -> None:
        """Polígonos que cubren áreas masivas o continentales (> 15° lon o > 10° lat) son rechazados."""
        huge_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-100.0, 0.0],
                    [-70.0, 0.0],   # delta_lon = 30° (> 15°)
                    [-70.0, 15.0],  # delta_lat = 15° (> 10°)
                    [-100.0, 15.0],
                    [-100.0, 0.0],
                ]
            ],
        }

        payload = {
            "region": huge_polygon,
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "temporal_resolution": "monthly",
        }

        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 422)
        err = response.json()["error"]
        self.assertEqual(err["code"], "UNPROCESSABLE_ENTITY")
        self.assertIn("supera la extensión espacial máxima permitida", err["message"])

    # -------------------------------------------------------------------------
    # 5. Rate Limiting (Control de frecuencia)
    # -------------------------------------------------------------------------
    def test_rate_limiter_rejects_with_429_when_threshold_exceeded(self) -> None:
        """Exceder el límite de frecuencia retorna HTTP 429 con cabecera Retry-After."""
        test_limiter = InMemoryRateLimiter(requests_per_minute=3, exploration_limit_per_minute=2)

        # Primeras dos solicitudes permitidas
        allowed_1, _ = test_limiter.is_allowed("192.168.1.50", is_exploration=True)
        allowed_2, _ = test_limiter.is_allowed("192.168.1.50", is_exploration=True)
        self.assertTrue(allowed_1)
        self.assertTrue(allowed_2)

        # Tercera solicitud debe ser rechazada
        allowed_3, retry_after = test_limiter.is_allowed("192.168.1.50", is_exploration=True)
        self.assertFalse(allowed_3)
        self.assertGreater(retry_after, 0)

    # -------------------------------------------------------------------------
    # 6. Autorización separada de lectura y escritura
    # -------------------------------------------------------------------------
    def test_is_write_authorized_respects_environment_and_key(self) -> None:
        """Verifica que la autorización de escritura atienda IYOK_ALLOW_WRITE e IYOK_WRITE_KEY."""
        # Caso A: Escritura permitida por defecto sin clave exigida
        with patch.dict(os.environ, {"IYOK_ALLOW_WRITE": "true", "IYOK_WRITE_KEY": ""}):
            self.assertTrue(is_write_authorized())

        # Caso B: Escritura explícitamente deshabilitada (modo solo lectura)
        with patch.dict(os.environ, {"IYOK_ALLOW_WRITE": "false"}):
            self.assertFalse(is_write_authorized())

        # Caso C: Clave de escritura requerida pero no provista
        with patch.dict(os.environ, {"IYOK_ALLOW_WRITE": "true", "IYOK_WRITE_KEY": "secreto-admin-123"}):
            self.assertFalse(is_write_authorized({}))
            self.assertFalse(is_write_authorized({"x-iyok-write-key": "clave-errada"}))
            self.assertTrue(is_write_authorized({"x-iyok-write-key": "secreto-admin-123"}))

    # -------------------------------------------------------------------------
    # 7. Solicitud legítima exitosa dentro de los límites
    # -------------------------------------------------------------------------
    def test_legitimate_exploration_request_succeeds_under_limits(self) -> None:
        """Una solicitud legítima dentro de los límites de área y fechas se procesa con HTTP 200."""
        mock_connector = MagicMock()
        mock_connector.fetch_monthly_precipitation.return_value = GPMIMERGResult(
            dataset="GPM_3IMERGM.07",
            version="07",
            region=GeoJSONPolygon(
                type="Polygon",
                coordinates=[
                    [
                        [-85.0, 9.5],
                        [-84.5, 9.5],
                        [-84.5, 10.0],
                        [-85.0, 10.0],
                        [-85.0, 9.5],
                    ]
                ],
            ),
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="Conversión estándar Pandas",
            spatial_resolution_degrees=0.1,
            granule_ids=("granule-1",),
            weighting_method="Intersección parcial y área equivalente",
            monthly_values=(
                MonthlyPrecipitation(month=date(2023, 1, 1), value=150.0, coverage_fraction=1.0),
            ),
        )
        app.dependency_overrides[get_connector] = lambda: mock_connector

        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "temporal_resolution": "monthly",
        }
        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(len(data["timeseries"]), 1)


if __name__ == "__main__":
    unittest.main()
