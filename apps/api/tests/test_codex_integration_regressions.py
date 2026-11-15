# Codex (Manuel): regresiones de integración para geometría, huecos y límites efectivos.
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
from app.core.security import rate_limiter
from app.main import app
from app.models.exploration import ExplorationRequest
from app.models.geojson import are_geometries_equal
from app.services.exploration_service import get_catalog, resolve_region
from app.services.trend_analysis import analyze_annual_trend
from fastapi.testclient import TestClient


def test_missing_years_are_inconclusive():
    years = list(range(2001, 2006)) + list(range(2020, 2025))
    frame = pd.DataFrame({"year": years, "annual_precipitation_mm": range(10)})
    result = analyze_annual_trend(frame)
    assert result.status == "inconclusive"
    assert result.p_value is None


def test_catalog_geometry_is_used_even_if_database_differs():
    client = MagicMock()
    req = ExplorationRequest(region_id="costa-rica-continental", variable_id="precipitation", start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))
    selected = resolve_region(req, client)
    assert are_geometries_equal(selected[0], get_catalog(client).regions[0].geom)
    client.table.assert_not_called()


def test_inner_rings_count_toward_vertex_limit():
    rate_limiter.reset()
    outer = [[-84, 10], [-83, 10], [-83, 11], [-84, 10]]
    hole = [[-83.9, 10.1], [-83.8, 10.1], [-83.8, 10.2]] * 200 + [[-83.9, 10.1]]
    payload = {"region": {"type": "Polygon", "coordinates": [outer, hole]}, "variable_id": "precipitation", "start_date": "2024-01-01", "end_date": "2024-01-31"}
    with TestClient(app) as client:
        response = client.post("/api/v1/explorations", json=payload)
    assert response.status_code == 422


def test_body_limit_enforced_without_content_length():
    rate_limiter.reset()
    with TestClient(app) as client:
        response = client.post("/api/v1/explorations", content=iter([b"x" * 600_000, b"y" * 600_000]), headers={"transfer-encoding": "chunked"})
    assert response.status_code == 413
