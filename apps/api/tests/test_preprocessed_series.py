import unittest
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.routes import get_optional_supabase
from app.main import app
from app.services.exploration_service import DEFAULT_COSTA_RICA_GEOM, DEFAULT_PANAMA_CANAL_GEOM
from app.services.preprocessed_series import load_preprocessed_series


class PreprocessedSeriesTests(unittest.TestCase):
    def test_subrange_preserves_values_and_corresponding_granules(self):
        series = load_preprocessed_series("costa-rica-continental", DEFAULT_COSTA_RICA_GEOM, date(2024, 1, 1), date(2024, 12, 31))
        self.assertIsNotNone(series)
        self.assertEqual(len(series.frame), 12)
        self.assertEqual(series.frame.iloc[0]["precipitation_mm"], 66.03)
        self.assertEqual(series.frame.iloc[-1]["precipitation_mm"], 212.60)
        self.assertEqual(len(series.metadata["source_granule_ids"]), 12)
        self.assertEqual(series.metadata["source_granule_ids"][0], "G3087531387-GES_DISC")

    def test_geometry_and_coverage_must_match(self):
        self.assertIsNone(load_preprocessed_series("costa-rica-continental", DEFAULT_PANAMA_CANAL_GEOM, date(2024, 1, 1), date(2024, 12, 31)))
        self.assertIsNone(load_preprocessed_series("costa-rica-continental", DEFAULT_COSTA_RICA_GEOM, date(2000, 1, 1), date(2024, 12, 31)))

    def test_auto_api_uses_file_without_remote_fetch_for_multiyear_range(self):
        app.dependency_overrides[get_optional_supabase] = lambda: None
        try:
            with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}), patch("app.services.gpm_imerg.GPMIMERGConnector.fetch_monthly_precipitation") as fetch:
                with TestClient(app) as client:
                    response = client.post("/api/v1/explorations", json={"region_id": "costa-rica-continental", "variable_id": "precipitation", "start_date": "2001-01-01", "end_date": "2024-12-31"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["timeseries"]), 288)
            self.assertEqual(response.json()["metadata"]["cache_status"], "preprocessed")
            trend = response.json()["trend_analysis"]
            self.assertEqual(trend["status"], "inconclusive")
            self.assertIsNone(trend["p_value"])
            self.assertIsNone(trend["is_significant"])
            fetch.assert_not_called()
        finally:
            app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
