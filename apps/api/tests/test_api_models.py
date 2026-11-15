import copy
import json
import unittest
from pathlib import Path

from app.models.catalog import CatalogResponse
from app.models.errors import ErrorResponse
from app.models.exploration import (
    ExplorationRequest,
    ExplorationResponse,
    TrendAnalysis,
)
from app.models.geojson import GeoJSONPolygon
from pydantic import ValidationError


class APIContractModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Busca en referencias/ (raíz del monorepo) o en la raíz de apps/api
        possible_paths = [
            Path(__file__).resolve().parents[3] / "referencias" / "iyok_api_contracts_mock.json",
            Path(__file__).resolve().parents[1] / "iyok_api_contracts_mock.json",
            Path(__file__).resolve().parents[2] / "iyok_api_contracts_mock.json",
        ]
        contract_path = next((p for p in possible_paths if p.exists()), possible_paths[0])
        data = json.loads(contract_path.read_text(encoding="utf-8"))
        cls.contract = data["api_contracts"]
        cls.errors = data.get("error_envelopes", {})

    def test_models_accept_v1_catalog_contract(self) -> None:
        catalog_mock = self.contract["GET_/api/v1/catalog"]["response"]
        catalog = CatalogResponse.model_validate(catalog_mock)
        self.assertEqual(catalog.model_dump(mode="json", exclude_unset=True), catalog_mock)
        self.assertGreaterEqual(len(catalog.regions), 1)
        self.assertGreaterEqual(len(catalog.variables), 1)
        self.assertGreaterEqual(len(catalog.combinations), 1)

    def test_models_accept_v1_exploration_contract(self) -> None:
        exploration = self.contract["POST_/api/v1/explorations"]
        request = ExplorationRequest.model_validate(exploration["request_body_example"])
        response = ExplorationResponse.model_validate(exploration["response"])
        alt_inconclusive = ExplorationResponse.model_validate(
            exploration["alternative_inconclusive_response"]
        )
        alt_not_computed = ExplorationResponse.model_validate(
            exploration["alternative_not_computed_response"]
        )

        self.assertEqual(request.model_dump(mode="json", exclude_none=True), exploration["request_body_example"])
        self.assertEqual(response.model_dump(mode="json", exclude_unset=True), exploration["response"])
        self.assertEqual(
            alt_inconclusive.model_dump(mode="json", exclude_unset=True),
            exploration["alternative_inconclusive_response"],
        )
        self.assertEqual(
            alt_not_computed.model_dump(mode="json", exclude_unset=True),
            exploration["alternative_not_computed_response"],
        )

    def test_error_envelopes_validate(self) -> None:
        for err_mock in self.errors.values():
            parsed = ErrorResponse.model_validate(err_mock)
            self.assertEqual(parsed.model_dump(mode="json"), err_mock)

    def test_request_rejects_variables_outside_the_mvp(self) -> None:
        request = copy.deepcopy(
            self.contract["POST_/api/v1/explorations"]["request_body_example"]
        )
        request["variable_id"] = "land_surface_temperature"

        with self.assertRaises(ValidationError):
            ExplorationRequest.model_validate(request)

    def test_polygon_ring_must_be_closed_when_passed(self) -> None:
        polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-85.0, 10.0],
                    [-84.0, 10.0],
                    [-84.0, 11.0],
                    [-85.0, 11.0],
                    [-85.4, 10.1],  # No cerrado
                ]
            ],
        }
        with self.assertRaises(ValidationError):
            GeoJSONPolygon.model_validate(polygon)

    def test_date_range_must_be_ordered(self) -> None:
        request = {
            "region_id": "costa-rica-continental",
            "variable_id": "precipitation",
            "start_date": "2024-01-01",
            "end_date": "2023-01-01",
        }
        with self.assertRaises(ValidationError):
            ExplorationRequest.model_validate(request)

    def test_polygon_coordinates_must_be_in_range(self) -> None:
        polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-181.0, 10.0],
                    [-84.0, 10.0],
                    [-84.0, 11.0],
                    [-85.0, 11.0],
                    [-181.0, 10.0],
                ]
            ],
        }
        with self.assertRaises(ValidationError):
            GeoJSONPolygon.model_validate(polygon)

    def test_trend_p_value_must_be_between_zero_and_one(self) -> None:
        response = copy.deepcopy(
            self.contract["POST_/api/v1/explorations"]["response"]
        )
        response["trend_analysis"]["p_value"] = 1.1

        with self.assertRaises(ValidationError):
            ExplorationResponse.model_validate(response)

    def test_inconclusive_trend_requires_methodological_note_and_no_metrics(
        self,
    ) -> None:
        trend = self.contract["POST_/api/v1/explorations"][
            "alternative_inconclusive_response"
        ]["trend_analysis"]
        missing_note = copy.deepcopy(trend)
        missing_note["methodological_note"] = None
        with self.assertRaises(ValidationError):
            TrendAnalysis.model_validate(missing_note)

        with_metrics = copy.deepcopy(trend)
        with_metrics["slope"] = 0.1
        with self.assertRaises(ValidationError):
            TrendAnalysis.model_validate(with_metrics)

    def test_not_computed_trend_requires_methodological_note_and_no_metrics(
        self,
    ) -> None:
        trend = self.contract["POST_/api/v1/explorations"][
            "alternative_not_computed_response"
        ]["trend_analysis"]
        self.assertEqual(trend["status"], "not_computed")
        missing_note = copy.deepcopy(trend)
        missing_note["methodological_note"] = None
        with self.assertRaises(ValidationError):
            TrendAnalysis.model_validate(missing_note)

        with_metrics = copy.deepcopy(trend)
        with_metrics["slope"] = 1.0
        with self.assertRaises(ValidationError):
            TrendAnalysis.model_validate(with_metrics)

    def test_conclusive_trend_requires_all_metrics(self) -> None:
        trend = copy.deepcopy(
            self.contract["POST_/api/v1/explorations"]["response"]["trend_analysis"]
        )
        self.assertEqual(
            TrendAnalysis.model_validate(trend).status,
            "conclusive",
        )
        trend["p_value"] = None
        with self.assertRaises(ValidationError):
            TrendAnalysis.model_validate(trend)


if __name__ == "__main__":
    unittest.main()
