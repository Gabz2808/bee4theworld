import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.api.routes import get_connector, get_optional_supabase
from app.main import app
from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation
from fastapi.testclient import TestClient


class APIEndpointsTests(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_optional_supabase] = lambda: None
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_get_ping(self) -> None:
        response = self.client.get("/ping")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_nasa_without_credentials_returns_clear_error(self) -> None:
        with patch("app.services.exploration_service.load_supabase_series") as cache, patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa", "EARTHDATA_TOKEN": ""}):
            response = self.client.post("/api/v1/explorations", json={
                "region_id": "costa-rica-continental", "variable_id": "precipitation",
                "start_date": "2024-01-01", "end_date": "2024-01-31",
                "temporal_resolution": "monthly",
            })
        cache.assert_not_called()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "NASA_AUTH_REQUIRED")

    def test_nasa_mode_does_not_use_supabase_and_rejects_unknown_mode(self) -> None:
        with patch("app.api.routes.get_supabase_client") as client:
            with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa"}):
                self.assertIsNone(get_optional_supabase())
            client.assert_not_called()
        app.dependency_overrides.pop(get_optional_supabase, None)
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "invalid"}):
            self.assertEqual(self.client.get("/api/v1/catalog").status_code, 503)

    def test_get_v1_catalog(self) -> None:
        response = self.client.get("/api/v1/catalog")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(len(data["regions"]), 1)
        self.assertGreaterEqual(len(data["variables"]), 1)
        self.assertGreaterEqual(len(data["combinations"]), 1)

        reg = data["regions"][0]
        self.assertEqual(reg["id"], "costa-rica-continental")
        self.assertEqual(reg["geom"]["type"], "Polygon")

        var = data["variables"][0]
        self.assertEqual(var["id"], "precipitation")
        self.assertEqual(var["unit"], "mm/month")
        self.assertIn("restrictions", var)

        comb = data["combinations"][0]
        self.assertEqual(comb["region_id"], "costa-rica-continental")
        self.assertEqual(comb["variable_id"], "precipitation")
        self.assertTrue(comb["is_ready_for_exploration"])

    def test_legacy_routes_are_not_found(self) -> None:
        res_reg = self.client.get("/api/regions")
        res_vars = self.client.get("/api/variables")
        res_exp = self.client.post("/api/exploration", json={})
        self.assertEqual(res_reg.status_code, 404)
        self.assertEqual(res_vars.status_code, 404)
        self.assertEqual(res_exp.status_code, 404)

    def test_exploration_rejects_unknown_region_id_with_404(self) -> None:
        payload = {
            "region_id": "region-inexistente",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "temporal_resolution": "monthly",
        }
        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 404)
        err = response.json()["error"]
        self.assertEqual(err["code"], "NOT_FOUND")
        self.assertIn("no existe en el catálogo", err["message"])

    def test_exploration_rejects_unaligned_start_date(self) -> None:
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "2023-01-15",  # No es día 1
            "end_date": "2023-01-31",
            "temporal_resolution": "monthly",
        }
        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 400)
        err = response.json()["error"]
        self.assertEqual(err["code"], "INVALID_REQUEST")
        self.assertIn("primer día", err["message"])

    def test_exploration_rejects_unaligned_end_date(self) -> None:
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-01-20",  # No es último día de mes
            "temporal_resolution": "monthly",
        }
        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 400)
        err = response.json()["error"]
        self.assertEqual(err["code"], "INVALID_REQUEST")
        self.assertIn("último día", err["message"])

    def test_exploration_rejects_date_out_of_imerg_range(self) -> None:
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "1999-01-01",  # Precede a 2001
            "end_date": "1999-12-31",
            "temporal_resolution": "monthly",
        }
        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 400)
        err = response.json()["error"]
        self.assertEqual(err["code"], "INVALID_REQUEST")
        self.assertIn("fuera del intervalo disponible", err["message"])

    def test_exploration_rejects_invalid_variable_with_422(self) -> None:
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "temperatura_superficial",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "temporal_resolution": "monthly",
        }
        response = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(response.status_code, 422)
        err = response.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")
        self.assertGreaterEqual(len(err["details"]), 1)

    def test_exploration_executes_successfully_with_region_id_and_v1(self) -> None:
        # Simular 24 meses de observaciones
        dates = [date(2023, m, 1) for m in range(1, 13)] + [date(2024, m, 1) for m in range(1, 13)]
        monthly_values = tuple(
            MonthlyPrecipitation(
                month=d,
                value=150.0 + (i % 6) * 30.0,
                coverage_fraction=1.0,
            )
            for i, d in enumerate(dates)
        )
        fake_region = GeoJSONPolygon(
            type="Polygon",
            coordinates=[
                [
                    [-85.0, 10.0],
                    [-84.0, 10.0],
                    [-84.0, 11.0],
                    [-85.0, 11.0],
                    [-85.0, 10.0],
                ]
            ],
        )
        simulated_result = GPMIMERGResult(
            dataset="GPM_3IMERGM",
            version="07",
            region=fake_region,
            source_units="mm/month",
            output_units="mm/month",
            unit_conversion="identity",
            spatial_resolution_degrees=0.1,
            granule_ids=tuple(f"GPM_GRANULE_{i}" for i in range(24)),
            weighting_method="equal_area_partial_cell_weighting",
            monthly_values=monthly_values,
        )

        mock_connector = MagicMock()
        mock_connector.fetch_monthly_precipitation.return_value = simulated_result

        # Inyectar mock
        app.dependency_overrides[get_connector] = lambda: mock_connector
        app.dependency_overrides[get_optional_supabase] = lambda: None
        try:
            # Prueba con region_id
            payload = {
                "region_id": "costa-rica-continental",
                "variable_id": "precipitation",
                "start_date": "2023-01-01",
                "end_date": "2024-12-31",
                "temporal_resolution": "monthly",
            }
            response = self.client.post("/api/v1/explorations", json=payload)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "success")

            # Metadatos y selección efectiva
            metadata = data["metadata"]
            self.assertEqual(metadata["unit"], "mm/month")
            self.assertEqual(metadata["source"], "NASA GES DISC mediante CMR y Harmony")
            self.assertEqual(metadata["source_units"], "mm/month")
            self.assertEqual(len(metadata["source_granule_ids"]), 24)
            self.assertIsNotNone(metadata["data_accessed_at"])
            self.assertIsNotNone(metadata["selection"])
            self.assertEqual(metadata["selection"]["region_id"], "costa-rica-continental")
            self.assertIn("warnings", metadata)
            self.assertGreaterEqual(len(metadata["warnings"]), 1)

            # Serie temporal y anomalías
            self.assertEqual(len(data["timeseries"]), 24)
            self.assertIn("anomaly_mm", data["timeseries"][0])
            self.assertIsNotNone(data["timeseries"][0]["anomaly_mm"])

            # Totales anuales
            self.assertEqual(len(data["annual_totals"]), 2)
            self.assertEqual(data["annual_totals"][0]["year"], 2023)
            self.assertEqual(data["annual_totals"][0]["months_reported"], 12)

            # Tendencia calculada
            self.assertIn("trend_analysis", data)
            self.assertIn(data["trend_analysis"]["status"], {"conclusive", "inconclusive"})

            # Interpretación científica comprensible y prudente
            self.assertIn("interpretation", data)
            interp = data["interpretation"]
            self.assertIsNotNone(interp)
            self.assertTrue(len(interp["headline"]) > 0)
            self.assertTrue(len(interp["narrative"]) > 0)
            self.assertTrue(len(interp["trend_verdict_plain_language"]) > 0)
            self.assertTrue(len(interp["anomaly_summary"]) > 0)
            self.assertGreaterEqual(len(interp["prudence_guidelines"]), 1)

            # Prueba con polígono personalizado directo en v1
            custom_payload = {
                "region": fake_region.model_dump(mode="json"),
                "variable_id": "precipitation",
                "start_date": "2023-01-01",
                "end_date": "2024-12-31",
                "temporal_resolution": "monthly",
            }
            custom_res = self.client.post("/api/v1/explorations", json=custom_payload)
            self.assertEqual(custom_res.status_code, 200)
            self.assertEqual(custom_res.json()["metadata"]["selection"]["region_id"], "custom-polygon")
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
