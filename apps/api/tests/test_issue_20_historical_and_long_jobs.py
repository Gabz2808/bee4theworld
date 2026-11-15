import time
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.api.routes import get_connector, get_optional_supabase
from app.main import app
from app.models.geojson import GeoJSONPolygon
from app.models.jobs import JobStatus
from app.services.exploration_service import MIN_SUPPORTED_DATE, get_catalog
from app.services.gpm_imerg import (
    DataUnavailableError,
    GPMIMERGConnector,
    GPMIMERGError,
    GPMIMERGResult,
    MonthlyPrecipitation,
)
from app.services.job_manager import JobManager, make_job_fingerprint
from fastapi.testclient import TestClient


class Issue20HistoricalAndLongJobsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.job_mgr = JobManager.get_instance()
        self.job_mgr.clear()

        self.geom = GeoJSONPolygon(
            type="Polygon",
            coordinates=[[
                [-85.0, 10.0],
                [-84.0, 10.0],
                [-84.0, 11.0],
                [-85.0, 11.0],
                [-85.0, 10.0],
            ]],
        )

        # Mock result para 1998
        self.mock_1998_result = GPMIMERGResult(
            dataset="GPM_3IMERGM.07",
            version="07",
            region=self.geom,
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="Conversión por horas de mes",
            spatial_resolution_degrees=0.1,
            granule_ids=("G3281475020-GES_DISC",),
            weighting_method="Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)",
            monthly_values=(
                MonthlyPrecipitation(
                    month=date(1998, 1, 1),
                    value=0.028,
                    coverage_fraction=1.0,
                ),
            ),
        )

    def tearDown(self) -> None:
        self.job_mgr.clear()
        app.dependency_overrides.clear()

    def test_min_supported_date_is_1998(self) -> None:
        """Criterio 1: La fecha mínima soportada es 1998-01-01."""
        self.assertEqual(MIN_SUPPORTED_DATE, date(1998, 1, 1))

    def test_catalog_advertises_1998_interval(self) -> None:
        """Criterio 1: El catálogo anuncia cobertura verificada desde 1998."""
        catalog = get_catalog()
        var = next(v for v in catalog.variables if v.id == "precipitation")
        self.assertEqual(var.available_interval.start, date(1998, 1, 1))
        self.assertEqual(var.verified_interval.start, date(1998, 1, 1))

        cr_combo = next(c for c in catalog.combinations if c.region_id == "costa-rica-continental")
        self.assertEqual(cr_combo.available_interval.start, date(1998, 1, 1))
        self.assertEqual(cr_combo.verified_interval.start, date(1998, 1, 1))
        self.assertIn("1998-2024", cr_combo.notes)

    def test_exploration_accepts_1998_dates(self) -> None:
        """Criterio 1: La API acepta fechas en 1998 y rechaza fechas en 1997."""
        # 1997 es rechazado con 400
        req_1997 = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "1997-01-01",
            "end_date": "1997-12-31",
            "temporal_resolution": "monthly",
        }
        resp_1997 = self.client.post("/api/v1/explorations", json=req_1997)
        self.assertEqual(resp_1997.status_code, 400)
        self.assertIn("fuera del intervalo disponible", resp_1997.json()["error"]["message"])

        # 1998 es aceptado con HTTP 200
        mock_connector = MagicMock()
        mock_connector.fetch_monthly_precipitation.return_value = self.mock_1998_result
        app.dependency_overrides[get_connector] = lambda: mock_connector

        req_1998 = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "1998-01-01",
            "end_date": "1998-01-31",
            "temporal_resolution": "monthly",
        }
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa"}):
            resp_1998 = self.client.post("/api/v1/explorations", json=req_1998)
        self.assertEqual(resp_1998.status_code, 200)
        data = resp_1998.json()
        self.assertEqual(len(data["timeseries"]), 1)
        self.assertEqual(data["timeseries"][0]["date"], "1998-01-01")

    def test_chunking_divides_multiyear_ranges(self) -> None:
        """Criterio 2: Rangos multianuales (> 12 meses) se dividen en bloques anuales."""
        connector = GPMIMERGConnector()
        # Mock de _fetch_chunk
        def mock_fetch_chunk(region, geom, months, start, end):
            return GPMIMERGResult(
                dataset="GPM_3IMERGM.07",
                version="07",
                region=region,
                source_units="mm/hr",
                output_units="mm/month",
                unit_conversion="test",
                spatial_resolution_degrees=0.1,
                granule_ids=tuple(f"G_{m:%Y%m}" for m in months),
                weighting_method="test",
                monthly_values=tuple(
                    MonthlyPrecipitation(month=m, value=10.0, coverage_fraction=1.0)
                    for m in months
                ),
            )

        connector._fetch_chunk = MagicMock(side_effect=mock_fetch_chunk)

        # 24 meses (1998-01-01 a 1999-12-31)
        res = connector.fetch_monthly_precipitation(
            self.geom,
            date(1998, 1, 1),
            date(1999, 12, 31),
        )
        # Se debieron procesar 2 bloques de 12 meses
        self.assertEqual(connector._fetch_chunk.call_count, 2)
        self.assertEqual(len(res.monthly_values), 24)
        self.assertEqual(len(res.granule_ids), 24)

    def test_chunking_retry_on_transient_failure(self) -> None:
        """Criterio 2: Reintento por bloque ante fallo transitorio."""
        connector = GPMIMERGConnector()
        calls = {"count": 0}

        def flaky_fetch_chunk(region, geom, months, start, end):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("Fallo transitorio de red simulado")
            return GPMIMERGResult(
                dataset="GPM_3IMERGM.07",
                version="07",
                region=region,
                source_units="mm/hr",
                output_units="mm/month",
                unit_conversion="test",
                spatial_resolution_degrees=0.1,
                granule_ids=("G1",),
                weighting_method="test",
                monthly_values=(
                    MonthlyPrecipitation(month=months[0], value=15.0, coverage_fraction=1.0),
                ),
            )

        connector._fetch_chunk = MagicMock(side_effect=flaky_fetch_chunk)

        # Rango de 24 meses donde el primer intento falla pero el reintento triunfa
        res = connector.fetch_monthly_precipitation(
            self.geom,
            date(1998, 1, 1),
            date(1999, 12, 31),
        )
        self.assertIsNotNone(res)
        # 1 intento fallido + 1 reintento exitoso (bloque 1) + 1 intento exitoso (bloque 2) = 3 llamadas
        self.assertEqual(connector._fetch_chunk.call_count, 3)

    def test_chunking_fails_cleanly_on_permanent_error(self) -> None:
        """Criterio 4: Si un bloque falla permanentemente tras reintentos, reporta fallo claro."""
        connector = GPMIMERGConnector()
        connector._fetch_chunk = MagicMock(side_effect=RuntimeError("Fallo persistente"))

        with self.assertRaises(DataUnavailableError) as ctx:
            connector.fetch_monthly_precipitation(
                self.geom,
                date(1998, 1, 1),
                date(1999, 12, 31),
            )
        self.assertIn("Error procesando bloque 1998", str(ctx.exception))

    def test_inflight_deduplication_prevents_duplicate_remote_requests(self) -> None:
        """Criterio 3: Deduplicación en vuelo evita duplicar peticiones remotas ante reintentos."""
        mock_connector = MagicMock()
        call_tracker = {"count": 0}

        def slow_fetch(geom, start, end, **kwargs):
            call_tracker["count"] += 1
            time.sleep(0.1)
            return self.mock_1998_result

        mock_connector.fetch_monthly_precipitation.side_effect = slow_fetch
        app.dependency_overrides[get_connector] = lambda: mock_connector

        req = {
            "region_id": "cuenca-canal-panama",
            "variable_id": "precipitation",
            "start_date": "1998-01-01",
            "end_date": "1998-01-31",
            "temporal_resolution": "monthly",
        }

        import concurrent.futures
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa"}):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(lambda: self.client.post("/api/v1/explorations", json=req))
                f2 = executor.submit(lambda: self.client.post("/api/v1/explorations", json=req))
                r1 = f1.result()
                r2 = f2.result()

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        # El conector remoto solo debe haberse llamado 1 sola vez gracias a la deduplicación
        self.assertEqual(call_tracker["count"], 1)

    def test_async_job_lifecycle(self) -> None:
        """Criterio 2: Ciclo de vida de trabajo asíncrono (creación 202, estado, progreso, deduplicación)."""
        mock_connector = MagicMock()
        mock_connector.fetch_monthly_precipitation.return_value = self.mock_1998_result
        app.dependency_overrides[get_connector] = lambda: mock_connector

        req = {
            "region_id": "cuenca-canal-panama",
            "variable_id": "precipitation",
            "start_date": "1998-01-01",
            "end_date": "1998-01-31",
            "temporal_resolution": "monthly",
        }

        # 1. Crear trabajo (POST /api/v1/jobs/explorations) -> 202 Accepted
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa"}):
            resp = self.client.post("/api/v1/jobs/explorations", json=req)
            self.assertEqual(resp.status_code, 202)
            data = resp.json()
            self.assertIn("job_id", data)
            job_id = data["job_id"]
            self.assertIn(data["status"], ["pending", "running", "completed"])

            # 2. Deduplicación de trabajo: enviar la misma consulta devuelve el mismo job_id
            resp2 = self.client.post("/api/v1/jobs/explorations", json=req)
            self.assertEqual(resp2.status_code, 202)
            self.assertEqual(resp2.json()["job_id"], job_id)

            # 3. Consultar estado del trabajo (GET /api/v1/jobs/{job_id})
            time.sleep(0.3)  # Dar tiempo para que el hilo complete
            status_resp = self.client.get(f"/api/v1/jobs/{job_id}")
            self.assertEqual(status_resp.status_code, 200)
            status_data = status_resp.json()
            self.assertEqual(status_data["status"], "completed")
            self.assertIsNotNone(status_data["result"])
            self.assertEqual(status_data["progress"]["percent"], 100.0)

    def test_async_job_cancellation(self) -> None:
        """Criterio 2: Cancelación de trabajo (DELETE /api/v1/jobs/{job_id})."""
        mock_connector = MagicMock()
        # Conector lento que se interrumpe
        def slow_fetch(geom, start, end, cancel_check=None, **kwargs):
            for _ in range(20):
                if cancel_check and cancel_check():
                    raise GPMIMERGError("Cancelado")
                time.sleep(0.05)
            return self.mock_1998_result

        mock_connector.fetch_monthly_precipitation.side_effect = slow_fetch
        app.dependency_overrides[get_connector] = lambda: mock_connector

        req = {
            "region_id": "cuenca-canal-panama",
            "variable_id": "precipitation",
            "start_date": "1998-01-01",
            "end_date": "1998-01-31",
            "temporal_resolution": "monthly",
        }

        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa"}):
            resp = self.client.post("/api/v1/jobs/explorations", json=req)
            self.assertEqual(resp.status_code, 202)
            job_id = resp.json()["job_id"]

            # Cancelar trabajo
            del_resp = self.client.delete(f"/api/v1/jobs/{job_id}")
            self.assertEqual(del_resp.status_code, 200)
            self.assertEqual(del_resp.json()["status"], "cancelled")

    def test_job_not_found_returns_404(self) -> None:
        resp = self.client.get("/api/v1/jobs/job-inexistente-1234")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["error"]["code"], "NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
