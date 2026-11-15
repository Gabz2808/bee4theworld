import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from app.core.cache import (
    load_from_cache,
    make_cache_key,
    save_to_cache,
    save_to_supabase,
)
from app.models.exploration import DateRange, ExplorationRequest
from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation


class CacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.geom = GeoJSONPolygon(
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
        self.start = date(2024, 1, 1)
        self.end = date(2024, 2, 29)
        self.df = pd.DataFrame(
            {
                "precipitation_mm": [150.5, 200.2],
                "coverage_fraction": [1.0, 1.0],
                "quality_flag": ["ok", "ok"],
            },
            index=pd.date_range("2024-01-01", periods=2, freq="MS"),
        )
        self.df.index.name = "month"

    def test_make_cache_key_deterministic(self) -> None:
        key1 = make_cache_key("precipitation", "costa-rica", self.geom, self.start, self.end)
        key2 = make_cache_key("precipitation", "costa-rica", self.geom, self.start, self.end)
        self.assertEqual(key1, key2)
        self.assertTrue(key1.startswith("precipitation_costa-rica_"))
        self.assertTrue(key1.endswith(".json"))

    def test_save_and_load_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.core.cache.get_cache_dir", return_value=Path(tmpdir)):
                # Cache miss
                miss = load_from_cache("precipitation", "cr", self.geom, self.start, self.end)
                self.assertIsNone(miss)

                # Save
                save_to_cache("precipitation", "cr", self.geom, self.start, self.end, self.df)

                # Cache hit
                hit = load_from_cache("precipitation", "cr", self.geom, self.start, self.end)
                self.assertIsNotNone(hit)
                self.assertEqual(len(hit), 2)
                self.assertAlmostEqual(hit.iloc[0]["precipitation_mm"], 150.5, places=2)

    def test_save_to_supabase_gracefully_handles_exceptions(self) -> None:
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = RuntimeError("Supabase network error")

        req = ExplorationRequest(
            variable_id="precipitation",
            region_id="costa-rica-continental",
            start_date=self.start,
            end_date=self.end,
        )
        result = GPMIMERGResult(
            dataset="GPM_3IMERGM.07",
            version="07",
            region=self.geom,
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="test",
            spatial_resolution_degrees=0.1,
            granule_ids=("G1",),
            weighting_method="test",
            monthly_values=(
                MonthlyPrecipitation(month=date(2024, 1, 1), value=0.2, coverage_fraction=1.0),
            ),
        )

        # Should not raise exception
        save_to_supabase(mock_supabase, req, self.geom, result, self.df, "costa-rica-continental")


if __name__ == "__main__":
    unittest.main()
