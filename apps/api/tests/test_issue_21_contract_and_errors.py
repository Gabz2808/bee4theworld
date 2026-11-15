import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.api.routes import get_connector, get_optional_supabase
from app.core.security import rate_limiter
from app.core.supabase_cache import SupabaseCacheOperationalError
from app.main import app
from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import (
    DataUnavailableError,
    EarthdataAuthenticationRequired,
    GPMIMERGConnector,
    GPMIMERGError,
    GPMIMERGResult,
    MonthlyPrecipitation,
)
from fastapi.testclient import TestClient


class Issue21ContractAndErrorsTests(unittest.TestCase):
    def setUp(self) -> None:
        rate_limiter.reset()
        self.client = TestClient(app)
        app.dependency_overrides[get_optional_supabase] = lambda: None
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
        self.mock_result = GPMIMERGResult(
            dataset="GPM_3IMERGM.07",
            version="07",
            region=self.geom,
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="Conversión de horas",
            spatial_resolution_degrees=0.1,
            granule_ids=("G1",),
            weighting_method="Área cilíndrica equivalente",
            monthly_values=(
                MonthlyPrecipitation(month=date(2023, 1, 1), value=0.05, coverage_fraction=1.0),
            ),
        )

    def tearDown(self) -> None:
        rate_limiter.reset()
        app.dependency_overrides.clear()

    # --- Criterio 2: Rechazo de solicitudes contradictorias y errores estables ---

    def test_rejects_contradictory_dates_between_start_end_and_date_range(self) -> None:
        """Criterio 2: Rechazar con 422 cuando date_range contradice start_date / end_date."""
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "date_range": {
                "start": "2024-01-01",  # Contradice start_date
                "end": "2024-12-31",
            },
            "temporal_resolution": "monthly",
        }
        resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 422)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")
        self.assertTrue(any("contradictoria de fechas" in d["issue"] for d in err["details"]))

    def test_rejects_custom_polygon_without_region_geometry(self) -> None:
        """Criterio 2: Rechazar con 422 cuando region_id es custom-polygon pero no se envía 'region'."""
        payload = {
            "region_id": "custom-polygon",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "temporal_resolution": "monthly",
        }
        resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 422)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "VALIDATION_ERROR")
        self.assertTrue(any("custom-polygon" in d["issue"] for d in err["details"]))

    def test_rejects_contradictory_region_geometry_with_stable_code(self) -> None:
        """Criterio 2: Rechazar con 422 y GEOMETRY_INCOMPATIBLE si region no coincide con region_id."""
        other_geom = {
            "type": "Polygon",
            "coordinates": [[
                [-80.0, 8.0],
                [-79.0, 8.0],
                [-79.0, 9.0],
                [-80.0, 9.0],
                [-80.0, 8.0],
            ]],
        }
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "region": other_geom,  # Geometría incompatible con Costa Rica
            "temporal_resolution": "monthly",
        }
        resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 422)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "GEOMETRY_INCOMPATIBLE")
        self.assertIn("Incompatibilidad geométrica", err["message"])

    def test_stable_error_for_out_of_coverage(self) -> None:
        """Criterio 2: Error estable en HTTP 400 para fechas fuera de cobertura."""
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "1995-01-01",
            "end_date": "1995-12-31",
            "temporal_resolution": "monthly",
        }
        resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 400)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "INVALID_REQUEST")

    def test_stable_error_for_unknown_region(self) -> None:
        """Criterio 2: Error estable NOT_FOUND en HTTP 404 para regiones inexistentes."""
        payload = {
            "region_id": "region-inexistente-xyz",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "temporal_resolution": "monthly",
        }
        resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 404)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "NOT_FOUND")

    def test_stable_error_for_missing_earthdata_token(self) -> None:
        """Criterio 2: Error estable NASA_AUTH_REQUIRED en HTTP 503 cuando falta token."""
        mock_connector = MagicMock()
        mock_connector.fetch_monthly_precipitation.side_effect = EarthdataAuthenticationRequired(
            "Configure EARTHDATA_TOKEN en el entorno"
        )
        app.dependency_overrides[get_connector] = lambda: mock_connector

        payload = {
            "region_id": "cuenca-canal-panama",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-01-31",
            "temporal_resolution": "monthly",
        }
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa"}):
            resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 503)
        err = resp.json()["error"]
        self.assertEqual(err["code"], "NASA_AUTH_REQUIRED")

    # --- Criterio 3: Distinguir caché ausente de fallo operativo ---

    def test_operational_cache_error_is_explicitly_reported_without_silent_degradation(self) -> None:
        """Criterio 3: Ante fallo operativo en Supabase, registrar error y advertir explícitamente en metadata."""
        mock_connector = MagicMock()
        mock_connector.fetch_monthly_precipitation.return_value = self.mock_result
        app.dependency_overrides[get_connector] = lambda: mock_connector

        mock_supabase = MagicMock()
        # Simular fallo operativo de conexión/BD
        with patch("app.services.exploration_service.load_supabase_series", side_effect=SupabaseCacheOperationalError("DB Connection Timeout")):
            with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}):
                payload = {
                    "region_id": "cuenca-canal-panama",
                    "variable_id": "precipitation",
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-31",
                    "temporal_resolution": "monthly",
                }
                app.dependency_overrides[get_optional_supabase] = lambda: mock_supabase
                resp = self.client.post("/api/v1/explorations", json=payload)

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        meta = data["metadata"]
        # Debe reflejar fallo operativo en advertencias
        self.assertTrue(any("Fallo operativo al consultar la caché Supabase" in w for w in meta["warnings"]))
        # El origen no debe degradarse silenciosamente
        self.assertEqual(meta["effective_origin"], "NASA Harmony")

    # --- Criterio 4: Pruebas de contrato API-cliente ---

    def test_client_contract_parse_catalog_compliance(self) -> None:
        """Criterio 4: El catálogo cumple estrictamente las reglas de parseCatalog de api-v1.ts."""
        resp = self.client.get("/api/v1/catalog")
        self.assertEqual(resp.status_code, 200)
        cat = resp.json()

        # Validación emulando parseCatalog de apps/web/src/app/lib/api-v1.ts
        self.assertEqual(cat["status"], "success")
        self.assertTrue(len(cat["regions"]) > 0)
        self.assertTrue(len(cat["variables"]) > 0)
        self.assertTrue(len(cat["combinations"]) > 0)

        for r in cat["regions"]:
            self.assertTrue(isinstance(r["id"], str) and r["id"])
            self.assertTrue(isinstance(r["name"], str) and r["name"])
            self.assertTrue(isinstance(r["boundary_source"], str))
            self.assertTrue(isinstance(r["boundary_version"], str))
            if r.get("geom") is not None:
                self.assertEqual(r["geom"]["type"], "Polygon")
                coords = r["geom"]["coordinates"]
                self.assertTrue(len(coords) >= 1)
                self.assertTrue(len(coords[0]) >= 4)
                # Anillo cerrado
                self.assertEqual(coords[0][0], coords[0][-1])

        for v in cat["variables"]:
            self.assertTrue(isinstance(v["id"], str))
            self.assertEqual(v["temporal_resolution"], "monthly")
            self.assertTrue(v["available_interval"]["start"] <= v["available_interval"]["end"])
            self.assertTrue(isinstance(v["restrictions"], list))

        for c in cat["combinations"]:
            self.assertTrue(isinstance(c["region_id"], str))
            self.assertTrue(isinstance(c["variable_id"], str))
            self.assertEqual(c["temporal_resolution"], "monthly")
            self.assertTrue(isinstance(c["is_ready_for_exploration"], bool))

    def test_client_contract_parse_exploration_compliance_with_real_series(self) -> None:
        """Criterio 4: Exploración real de Costa Rica cumple exactamente parseExploration de api-v1.ts."""
        payload = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "temporal_resolution": "monthly",
        }
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}):
            resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Emulación exacta de validaciones de parseExploration en api-v1.ts
        self.assertEqual(data["status"], "success")
        meta = data["metadata"]
        self.assertEqual(meta["temporal_resolution"], "monthly")
        sel = meta["selection"]
        self.assertEqual(sel["region_id"], payload["region_id"])
        self.assertEqual(sel["requested_period"]["start"], payload["start_date"])
        self.assertEqual(sel["requested_period"]["end"], payload["end_date"])
        self.assertEqual(sel["effective_period"]["start"], payload["start_date"])
        self.assertEqual(sel["effective_period"]["end"], payload["end_date"])

        # trend_analysis
        ta = data["trend_analysis"]
        self.assertIn(ta["status"], ["conclusive", "inconclusive", "not_computed"])
        if ta["status"] == "conclusive":
            self.assertIsNotNone(ta["slope"])
            self.assertIsNotNone(ta["p_value"])
            self.assertTrue(0 <= ta["p_value"] <= 1)
        else:
            self.assertIsNotNone(ta["methodological_note"])
            for metric in ["slope", "slope_unit", "p_value", "confidence_level", "is_significant"]:
                self.assertIsNone(ta.get(metric))

        # timeseries: meses únicos, consecutivos, empezando en start_date y con fechas YYYY-MM-01
        ts = data["timeseries"]
        self.assertEqual(len(ts), 12)
        expected_months = [f"2023-{m:02d}-01" for m in range(1, 13)]
        for i, point in enumerate(ts):
            self.assertEqual(point["date"], expected_months[i])
            self.assertIn(point["quality_flag"], ["ok", "partial_coverage", "missing_value", "missing_month"])
            self.assertTrue(0.0 <= point["coverage_fraction"] <= 1.0)
            if point["value"] is not None:
                self.assertTrue(point["value"] >= 0)

        # annual_totals
        totals = data["annual_totals"]
        self.assertEqual(len(totals), 1)
        self.assertEqual(totals[0]["year"], 2023)
        self.assertEqual(totals[0]["months_reported"], 12)
        self.assertTrue(totals[0]["annual_precipitation_mm"] >= 0)

    def test_client_contract_handles_missing_months_and_partial_coverage(self) -> None:
        """Criterio 4: Contrato soporta meses con null, flags missing_month y partial_coverage sin romper parseExploration."""
        mock_connector = MagicMock()
        dates_tuple = tuple(date(2023, m, 1) for m in range(1, 13))
        # Crear serie con un mes parcial (julio, cov 0.8) y un mes faltante (agosto, value None, cov 0.0)
        monthly_vals = []
        for m in range(1, 13):
            if m == 7:
                monthly_vals.append(MonthlyPrecipitation(month=dates_tuple[m - 1], value=0.1, coverage_fraction=0.8))
            elif m == 8:
                monthly_vals.append(MonthlyPrecipitation(month=dates_tuple[m - 1], value=None, coverage_fraction=0.0))
            else:
                monthly_vals.append(MonthlyPrecipitation(month=dates_tuple[m - 1], value=0.1, coverage_fraction=1.0))

        mock_result = GPMIMERGResult(
            dataset="GPM_3IMERGM.07",
            version="07",
            region=self.geom,
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="Conversión",
            spatial_resolution_degrees=0.1,
            granule_ids=tuple(f"G{m}" for m in range(1, 13)),
            weighting_method="Área equivalente",
            monthly_values=tuple(monthly_vals),
        )
        mock_connector.fetch_monthly_precipitation.return_value = mock_result
        app.dependency_overrides[get_connector] = lambda: mock_connector

        payload = {
            "region_id": "cuenca-canal-panama",
            "variable_id": "precipitation",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "temporal_resolution": "monthly",
        }
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "nasa"}):
            resp = self.client.post("/api/v1/explorations", json=payload)
        self.assertEqual(resp.status_code, 200)
        ts = resp.json()["timeseries"]

        # Julio: partial_coverage
        jul = ts[6]
        self.assertEqual(jul["date"], "2023-07-01")
        self.assertEqual(jul["quality_flag"], "partial_coverage")
        self.assertAlmostEqual(jul["coverage_fraction"], 0.8, places=4)

        # Agosto: missing_month
        aug = ts[7]
        self.assertEqual(aug["date"], "2023-08-01")
        self.assertIsNone(aug["value"])
        self.assertIn(aug["quality_flag"], ["missing_value", "missing_month"])


if __name__ == "__main__":
    unittest.main()
