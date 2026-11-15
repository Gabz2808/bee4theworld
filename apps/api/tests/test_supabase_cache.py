import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
from app.api.routes import get_connector, get_optional_supabase
from app.core.supabase_cache import load_supabase_series, save_supabase_series
from app.main import app
from app.models.exploration import ExplorationRequest
from app.models.geojson import GeoJSONPolygon
from app.services.exploration_service import run_exploration
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation
from fastapi.testclient import TestClient
from shapely import from_wkt
from shapely.geometry import mapping


class FakeQuery:
    def __init__(self, store, table):
        self.store, self.table_name, self.filters, self.payload = store, table, [], None
        self.maximum = 1000

    def select(self, fields): return self
    def limit(self, number): self.maximum = number; return self
    def order(self, key, **kwargs): return self
    def eq(self, key, value): self.filters.append((key, "eq", value)); return self
    def lte(self, key, value): self.filters.append((key, "lte", value)); return self
    def gte(self, key, value): self.filters.append((key, "gte", value)); return self
    def insert(self, payload): self.payload = payload; return self

    def execute(self):
        if self.payload is not None:
            values = self.payload if isinstance(self.payload, list) else [self.payload]
            stored = []
            for value in values:
                row = dict(value)
                if self.table_name == "ingestion_runs":
                    row["id"] = f"run-{len(self.store['ingestion_runs'])}"
                    row["created_at"] = "2026-11-14T12:00:00+00:00"
                    row["region_geometry_snapshot"] = mapping(from_wkt(row["region_geometry_snapshot"].split(";", 1)[1]))
                stored.append(row)
            self.store[self.table_name].extend(stored)
            return SimpleNamespace(data=stored)
        values = self.store[self.table_name]
        for key, op, value in self.filters:
            if op == "eq": values = [r for r in values if r.get(key) == value]
            if op == "lte": values = [r for r in values if r.get(key) <= value]
            if op == "gte": values = [r for r in values if r.get(key) >= value]
        return SimpleNamespace(data=values[:self.maximum])


class FakeSupabase:
    def __init__(self, geom):
        self.store = {"regions": [{"id": "00000000-0000-0000-0000-000000000001", "name": "Costa Rica Continental", "geom": geom.model_dump(mode="json")}], "ingestion_runs": [], "processed_data": []}
    def table(self, name): return FakeQuery(self.store, name)


class SupabaseCacheTests(unittest.TestCase):
    def setUp(self):
        self.geom = GeoJSONPolygon(type="Polygon", coordinates=[[[-85, 10], [-84.9, 10], [-84.9, 10.1], [-85, 10]]])
        self.start, self.end = date(2024, 1, 1), date(2024, 2, 29)
        self.client = FakeSupabase(self.geom)
        self.frame = pd.DataFrame({"precipitation_mm": [10.0, 20.0], "coverage_fraction": [1.0, 1.0], "quality_flag": ["ok", "ok"]}, index=pd.date_range("2024-01-01", periods=2, freq="MS", name="month"))
        self.result = GPMIMERGResult(dataset="GPM_3IMERGM.07", version="07", region=self.geom, source_units="mm/hr", output_units="mm/month", unit_conversion="conversion", spatial_resolution_degrees=0.1, granule_ids=("G1", "G2"), weighting_method="área", monthly_values=(MonthlyPrecipitation(date(2024, 1, 1), 10/744, 1.0), MonthlyPrecipitation(date(2024, 2, 1), 20/696, 1.0)))

    def test_complete_series_can_be_read_for_a_subrange(self):
        self.assertTrue(save_supabase_series(self.client, "costa-rica-continental", self.geom, self.start, self.end, self.result, self.frame))
        cached = load_supabase_series(self.client, "costa-rica-continental", self.geom, self.start, date(2024, 1, 31))
        self.assertIsNotNone(cached)
        self.assertEqual(cached.frame.iloc[0]["precipitation_mm"], 10.0)
        self.assertEqual(cached.metadata["source_units"], "mm/hr")

    def test_incomplete_or_other_geometry_is_never_a_hit(self):
        self.assertFalse(save_supabase_series(self.client, "custom-polygon", self.geom, self.start, self.end, self.result, self.frame))
        self.assertEqual(self.client.store["ingestion_runs"], [])
        self.assertTrue(save_supabase_series(self.client, "costa-rica-continental", self.geom, self.start, self.end, self.result, self.frame))
        self.client.store["processed_data"].pop()
        self.assertIsNone(load_supabase_series(self.client, "costa-rica-continental", self.geom, self.start, date(2024, 1, 31)))
        other = GeoJSONPolygon(type="Polygon", coordinates=[[[-84, 9], [-83.9, 9], [-83.9, 9.1], [-84, 9]]])
        self.assertIsNone(load_supabase_series(self.client, "costa-rica-continental", other, self.start, self.end))

    def test_nasa_is_only_called_once_for_repeated_request(self):
        connector = MagicMock()
        connector.fetch_monthly_precipitation.return_value = self.result
        request = ExplorationRequest(region_id="costa-rica-continental", variable_id="precipitation", start_date=self.start, end_date=self.end)
        region = (self.geom, "costa-rica-continental", "Costa Rica Continental", "provisional", "1", None)
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}), patch("app.services.exploration_service.resolve_region", return_value=region):
            first = run_exploration(request, connector=connector, supabase_client=self.client)
            second = run_exploration(request, connector=connector, supabase_client=self.client)
        self.assertEqual(first.metadata.cache_status, "stored")
        self.assertEqual(second.metadata.cache_status, "hit")
        self.assertEqual(connector.fetch_monthly_precipitation.call_count, 1)
        self.assertEqual([p.value for p in first.timeseries], [p.value for p in second.timeseries])

    def test_api_returns_cached_response_on_second_request(self):
        connector = MagicMock()
        connector.fetch_monthly_precipitation.return_value = self.result
        payload = {"region_id": "costa-rica-continental", "variable_id": "precipitation", "start_date": "2024-01-01", "end_date": "2024-02-29"}
        region = (self.geom, "costa-rica-continental", "Costa Rica Continental", "provisional", "1", None)
        app.dependency_overrides[get_connector] = lambda: connector
        app.dependency_overrides[get_optional_supabase] = lambda: self.client
        try:
            with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}), patch("app.services.exploration_service.resolve_region", return_value=region):  # noqa: SIM117 - keep the test setup readable
                with TestClient(app) as client:
                    first = client.post("/api/v1/explorations", json=payload)
                    second = client.post("/api/v1/explorations", json=payload)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(first.json()["metadata"]["cache_status"], "stored")
            self.assertEqual(second.json()["metadata"]["cache_status"], "hit")
            self.assertEqual(first.json()["timeseries"], second.json()["timeseries"])
            self.assertEqual(connector.fetch_monthly_precipitation.call_count, 1)
        finally:
            app.dependency_overrides.clear()

    # Codex (Manuel): la caché interna no necesita exponer la clave de escritura al navegador.
    def test_cache_write_respects_server_switch_without_client_key(self):
        connector = MagicMock()
        connector.fetch_monthly_precipitation.return_value = self.result
        request = ExplorationRequest(region_id="costa-rica-continental", variable_id="precipitation", start_date=self.start, end_date=self.end)
        region = (self.geom, "costa-rica-continental", "Costa Rica Continental", "provisional", "1", None)
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto", "IYOK_ALLOW_WRITE": "true", "IYOK_WRITE_KEY": "test-key"}), patch("app.services.exploration_service.resolve_region", return_value=region):
            response = run_exploration(request, connector=connector, supabase_client=self.client)
            self.assertEqual(response.metadata.cache_status, "stored")
        self.client = FakeSupabase(self.geom)
        with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto", "IYOK_ALLOW_WRITE": "false"}), patch("app.services.exploration_service.resolve_region", return_value=region):
            run_exploration(request, connector=connector, supabase_client=self.client)
            self.assertEqual(self.client.store["ingestion_runs"], [])


if __name__ == "__main__": unittest.main()
