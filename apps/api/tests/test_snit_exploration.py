import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import get_optional_supabase
from app.main import app
from app.services.snit_series import GEOMETRY_SHA, REGION_ID
from app.services import snit_series


class SNITExplorationTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[get_optional_supabase] = lambda: None
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_catalog_and_real_series_have_same_geometry(self):
        data = self.client.get("/api/v1/catalog").json()
        region = next(r for r in data["regions"] if r["id"] == REGION_ID)
        combination = next(c for c in data["combinations"] if c["region_id"] == REGION_ID)
        self.assertTrue(combination["is_ready_for_exploration"])
        self.assertIsNone(region["geom"])
        self.assertEqual(region["geometry_sha256"], GEOMETRY_SHA)
        response = self.client.post("/api/v1/explorations", json={"region_id": REGION_ID, "variable_id": "precipitation", "start_date": "2024-01-01", "end_date": "2024-12-31"})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["metadata"]["selection"]["geometry_sha256"], GEOMETRY_SHA)
        self.assertEqual(result["metadata"]["effective_origin"], "NASA Harmony")
        self.assertEqual(result["metadata"]["source"], "NASA GES DISC CMR/Harmony, recortes locales verificados")
        self.assertIsNone(result["metadata"]["geometry_snapshot"])
        self.assertIsNone(result["metadata"]["data_accessed_at"])
        self.assertEqual(len(result["timeseries"]), 12)
        self.assertEqual(result["timeseries"][0]["value"], 70.38)
        self.assertLess(result["timeseries"][0]["coverage_fraction"], 1)
        self.assertNotEqual(result["timeseries"][0]["value"], 66.03)

    def test_missing_series_disables_catalog_and_never_falls_back(self):
        with patch("app.services.exploration_service.load_snit", return_value=None), patch("app.services.exploration_service.GPMIMERGConnector") as connector:
            data = self.client.get("/api/v1/catalog").json()
            combination = next(c for c in data["combinations"] if c["region_id"] == REGION_ID)
            self.assertFalse(combination["is_ready_for_exploration"])
            response = self.client.post("/api/v1/explorations", json={"region_id": REGION_ID, "start_date": "2024-01-01", "end_date": "2024-01-31"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["error"]["code"], "SNIT_SERIES_UNAVAILABLE")
            connector.assert_not_called()

    def test_corrupt_file_or_geometry_disables_snit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with patch.object(snit_series, "SERIES", path):
                self.assertIsNone(snit_series.load_snit())
            geometry = Path(tmp) / "bad.gz"
            geometry.write_bytes(b"corrupt")
            with patch.object(snit_series, "GEOMETRY", geometry):
                self.assertIsNone(snit_series.load_snit())


if __name__ == "__main__":
    unittest.main()
