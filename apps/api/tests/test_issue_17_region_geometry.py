"""Pruebas para Issue #17: Backend 3/7 - Validar geometría de Costa Rica e identificadores de región.

Verifica:
1. Procedencia oficial de la geometría de Costa Rica en catálogo y respuestas (IGN/WDC 2024).
2. Separación estricta entre identificador público estable ('costa-rica-continental') y UUID interno de Supabase.
3. Rechazo con HTTP 422 ante incompatibilidad geométrica entre region_id y el polígono provisto.
4. Omisión determinista de ingestas en Supabase si el snapshot geométrico no coincide con la consulta.
5. Compatibilidad total con el validador estricto del cliente frontend v1 (api-v1.ts).
"""
from __future__ import annotations

import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
from app.core.cache import save_to_supabase
from app.main import app
from app.models.exploration import ExplorationRequest
from app.models.geojson import GeoJSONPolygon, are_geometries_equal
from app.services.exploration_service import (
    DEFAULT_COSTA_RICA_GEOM,
    _fetch_from_supabase,
    get_catalog,
    resolve_region,
    run_exploration,
    validate_exploration_request,
)
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation
from fastapi import HTTPException
from fastapi.testclient import TestClient


class Issue17RegionGeometryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.mock_cr_uuid = "96bdd25d-7fed-4b9e-b2ac-23a197a5d2d5"
        self.differing_geom = GeoJSONPolygon(
            type="Polygon",
            coordinates=[
                [
                    [-84.0, 9.0],
                    [-83.0, 9.0],
                    [-83.0, 10.0],
                    [-84.0, 10.0],
                    [-84.0, 9.0],
                ]
            ],
        )

    # -------------------------------------------------------------------------
    # Criterio 1: Catálogo y Geometría Oficial de Costa Rica (IGN/WDC 2024)
    # -------------------------------------------------------------------------
    # Codex (Manuel): comprobar identidad pública y procedencia provisional.
    def test_catalog_exposes_public_id_and_provisional_geometry(self):
        """El catálogo identifica la geometría aproximada sin atribuirle oficialidad."""
        catalog = get_catalog()
        cr = next((r for r in catalog.regions if r.id == "costa-rica-continental"), None)
        self.assertIsNotNone(cr, "La región 'costa-rica-continental' debe existir en el catálogo")
        # Codex (Manuel): no atribuir oficialidad a la geometría hasta verificar su procedencia.
        self.assertEqual(cr.boundary_version, "provisional")
        self.assertIn("no verificada", cr.boundary_source)
        self.assertTrue(
            are_geometries_equal(cr.geom, DEFAULT_COSTA_RICA_GEOM),
            "La geometría en catálogo debe coincidir con DEFAULT_COSTA_RICA_GEOM",
        )

    # -------------------------------------------------------------------------
    # Criterio 2: Separación de Identificador Público Estable y UUID Interno
    # -------------------------------------------------------------------------
    @patch.dict(os.environ, {"IYOK_DATA_SOURCE": "nasa"})
    def test_nasa_mode_returns_public_slug_in_selection(self):
        """En modo NASA, selection.region_id es exactamente el identificador público solicitado."""
        req = ExplorationRequest(
            region_id="costa-rica-continental",
            variable_id="precipitation",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        fake_result = GPMIMERGResult(
            dataset="GPM_3IMERGM",
            version="07",
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="hours_in_month * rate",
            spatial_resolution_degrees=0.1,
            weighting_method="equal_area_reprojection (EPSG:6933)",
            granule_ids=("G1",),
            region=DEFAULT_COSTA_RICA_GEOM,
            monthly_values=tuple(
                MonthlyPrecipitation(
                    month=date(2023, m, 1),
                    value=150.0,
                    coverage_fraction=1.0,
                )
                for m in range(1, 13)
            ),
        )
        connector_mock = MagicMock()
        connector_mock.fetch_monthly_precipitation.return_value = fake_result

        response = run_exploration(req, connector=connector_mock)
        self.assertEqual(
            response.metadata.selection.region_id,
            "costa-rica-continental",
            "selection.region_id debe coincidir con el identificador público solicitado",
        )
        # Codex (Manuel): la selección conserva la procedencia provisional publicada en el catálogo.
        self.assertEqual(response.metadata.selection.boundary_version, "provisional")
        self.assertIn("no verificada", response.metadata.selection.boundary_source)

    @patch.dict(os.environ, {"IYOK_DATA_SOURCE": "auto"})
    def test_auto_mode_with_supabase_returns_public_slug_never_internal_uuid(self):
        """Cuando Supabase devuelve un registro con UUID interno, selection.region_id se mantiene como 'costa-rica-continental'."""
        req = ExplorationRequest(
            region_id="costa-rica-continental",
            variable_id="precipitation",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        mock_supabase = MagicMock()
        # Mock para consulta de regions
        mock_supabase.table().select().eq().limit().execute.return_value = MagicMock(
            data=[
                {
                    "id": self.mock_cr_uuid,
                    "name": "Costa Rica Continental",
                    "boundary_source": "Instituto Geográfico Nacional (IGN) Costa Rica / WDC Cartography",
                    "boundary_version": "2024",
                    "geom": DEFAULT_COSTA_RICA_GEOM.model_dump(),
                }
            ]
        )
        # Mock para ingestion_runs y processed_data (para simular HIT de caché)
        mock_supabase.table().select().eq().eq().lte().gte().order().execute.return_value = MagicMock(
            data=[
                {
                    "id": "run-test-123",
                    "region_geometry_snapshot": DEFAULT_COSTA_RICA_GEOM.model_dump(),
                }
            ]
        )
        expected_rows = [
            {
                "observed_month": f"2023-{m:02d}-01",
                "precipitation_mm": 150.0,
                "coverage_fraction": 1.0,
                "quality_flag": "ok",
            }
            for m in range(1, 13)
        ]
        mock_supabase.table().select().eq().gte().lte().order().execute.return_value = MagicMock(
            data=expected_rows
        )

        # Codex (Manuel): aislar la prueba de contrato de solicitudes reales a NASA.
        connector_mock = MagicMock()
        connector_mock.fetch_monthly_precipitation.return_value = GPMIMERGResult(
            dataset="GPM_3IMERGM.07", version="07", source_units="mm/hr",
            output_units="mm/month", unit_conversion="hours_in_month * rate",
            spatial_resolution_degrees=0.1, weighting_method="equal_area_reprojection",
            granule_ids=tuple(f"G{m}" for m in range(1, 13)), region=DEFAULT_COSTA_RICA_GEOM,
            monthly_values=tuple(MonthlyPrecipitation(month=date(2023, m, 1), value=150.0, coverage_fraction=1.0) for m in range(1, 13)),
        )
        response = run_exploration(req, supabase_client=mock_supabase, connector=connector_mock)
        # Verificación crítica: NO debe ser el UUID, sino 'costa-rica-continental'
        self.assertEqual(
            response.metadata.selection.region_id,
            "costa-rica-continental",
            "selection.region_id nunca debe exponer el UUID interno de Supabase cuando se solicita por slug",
        )
        self.assertNotEqual(
            response.metadata.selection.region_id,
            self.mock_cr_uuid,
            "El UUID interno de Supabase no debe sustituir al identificador público",
        )

    def test_direct_uuid_request_resolves_and_preserves_contract(self):
        """Si un cliente solicita directamente por UUID, se resuelve y la respuesta refleja el identificador solicitado."""
        req = ExplorationRequest(
            region_id=self.mock_cr_uuid,
            variable_id="precipitation",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        mock_supabase = MagicMock()
        mock_supabase.table().select().eq().limit().execute.return_value = MagicMock(
            data=[
                {
                    "id": self.mock_cr_uuid,
                    "name": "Costa Rica Continental",
                    "boundary_source": "Instituto Geográfico Nacional (IGN) Costa Rica / WDC Cartography",
                    "boundary_version": "2024",
                    "geom": DEFAULT_COSTA_RICA_GEOM.model_dump(),
                }
            ]
        )
        geom, public_id, name, _src, _ver, internal_uuid = resolve_region(req, mock_supabase)
        self.assertEqual(public_id, self.mock_cr_uuid)
        self.assertEqual(internal_uuid, self.mock_cr_uuid)
        self.assertEqual(name, "Costa Rica Continental")
        self.assertTrue(are_geometries_equal(geom, DEFAULT_COSTA_RICA_GEOM))

    # -------------------------------------------------------------------------
    # Criterio 3: Incompatibilidad Geométrica (Rechazo 422)
    # -------------------------------------------------------------------------
    def test_geometric_mismatch_between_region_id_and_region_rejected_with_422(self):
        """Una solicitud con region_id='costa-rica-continental' y geometría distinta es rechazada con HTTP 422."""
        req = ExplorationRequest(
            region_id="costa-rica-continental",
            region=self.differing_geom,
            variable_id="precipitation",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        with self.assertRaises(HTTPException) as ctx:
            validate_exploration_request(req)
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("Incompatibilidad geométrica", ctx.exception.detail)

    def test_identical_geometry_in_region_and_region_id_is_accepted(self):
        """Una solicitud con region_id='costa-rica-continental' y la misma geometría oficial es aceptada."""
        req = ExplorationRequest(
            region_id="costa-rica-continental",
            region=DEFAULT_COSTA_RICA_GEOM,
            variable_id="precipitation",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        # No debe lanzar excepción
        validate_exploration_request(req)
        geom, public_id, _name, _src, _ver, _ = resolve_region(req)
        self.assertEqual(public_id, "costa-rica-continental")
        self.assertTrue(are_geometries_equal(geom, DEFAULT_COSTA_RICA_GEOM))

    def test_ingestion_snapshot_geometry_mismatch_skipped_by_supabase_reader(self):
        """_fetch_from_supabase descarta un run en Supabase cuyo region_geometry_snapshot no coincide con la geometría consultada."""
        req = ExplorationRequest(
            region_id="costa-rica-continental",
            variable_id="precipitation",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        mock_supabase = MagicMock()
        # regions
        mock_supabase.table().select().eq().limit().execute.return_value = MagicMock(
            data=[{"id": self.mock_cr_uuid, "name": "Costa Rica Continental"}]
        )
        # ingestion_runs devuelve un snapshot incompatible
        mock_supabase.table().select().eq().eq().lte().gte().order().execute.return_value = MagicMock(
            data=[
                {
                    "id": "run-incompatible-999",
                    "region_geometry_snapshot": self.differing_geom.model_dump(),
                }
            ]
        )
        df = _fetch_from_supabase(
            mock_supabase,
            req,
            date(2023, 1, 1),
            date(2023, 12, 31),
            region_identifier="costa-rica-continental",
            geom=DEFAULT_COSTA_RICA_GEOM,
        )
        self.assertIsNone(df, "El lector de Supabase debe omitir el run con snapshot geométrico discordante")

    @patch("app.core.cache.is_write_authorized", return_value=True)
    def test_save_to_supabase_skips_write_on_geometry_mismatch(self, _mock_auth):
        """save_to_supabase no inserta en Supabase si la geometría a persistir difiere de la registrada en public.regions."""
        mock_supabase = MagicMock()
        # regions retorna la geometría oficial de Costa Rica
        mock_supabase.table().select().eq().limit().execute.return_value = MagicMock(
            data=[
                {
                    "id": self.mock_cr_uuid,
                    "name": "Costa Rica Continental",
                    "geom": DEFAULT_COSTA_RICA_GEOM.model_dump(),
                }
            ]
        )
        req = ExplorationRequest(
            region_id="costa-rica-continental",
            variable_id="precipitation",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        fake_result = MagicMock()
        # Intentamos guardar con una geometría diferente
        save_to_supabase(
            mock_supabase,
            req,
            geom=self.differing_geom,
            result=fake_result,
            monthly_frame=pd.DataFrame(),
            region_identifier="costa-rica-continental",
        )
        # Verificar que NO se intentó insertar en ingestion_runs
        mock_supabase.table("ingestion_runs").insert.assert_not_called()

    # -------------------------------------------------------------------------
    # Criterio 4: Consumo por Cliente Frontend v1
    # -------------------------------------------------------------------------
    @patch.dict(os.environ, {"IYOK_DATA_SOURCE": "nasa"})
    def test_client_v1_contract_consumed_successfully_via_endpoint(self):
        """Prueba de extremo a extremo mediante el endpoint HTTP comprobando que la respuesta cumple con api-v1.ts."""
        fake_result = GPMIMERGResult(
            dataset="GPM_3IMERGM",
            version="07",
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="hours_in_month * rate",
            spatial_resolution_degrees=0.1,
            weighting_method="equal_area_reprojection (EPSG:6933)",
            granule_ids=("G1",),
            region=DEFAULT_COSTA_RICA_GEOM,
            monthly_values=tuple(
                MonthlyPrecipitation(
                    month=date(2023, m, 1),
                    value=150.0,
                    coverage_fraction=1.0,
                )
                for m in range(1, 13)
            ),
        )
        with patch(
            "app.services.exploration_service.GPMIMERGConnector.fetch_monthly_precipitation",
            return_value=fake_result,
        ):
            payload = {
                "region_id": "costa-rica-continental",
                "variable_id": "precipitation",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            }
            res = self.client.post("/api/v1/explorations", json=payload)
            self.assertEqual(res.status_code, 200)
            data = res.json()

            # Validación de campos requeridos por parseExploration en apps/web/src/app/lib/api-v1.ts:
            self.assertEqual(data["status"], "success")
            metadata = data["metadata"]
            selection = metadata["selection"]
            # Exigencia 1: selection.region_id === request.region_id
            self.assertEqual(selection["region_id"], payload["region_id"])
            # Exigencia 2: requested_period y effective_period coinciden con las fechas de la solicitud
            self.assertEqual(selection["requested_period"]["start"], payload["start_date"])
            self.assertEqual(selection["requested_period"]["end"], payload["end_date"])
            self.assertEqual(selection["effective_period"]["start"], payload["start_date"])
            self.assertEqual(selection["effective_period"]["end"], payload["end_date"])
            # Exigencia 3: temporal_resolution == "monthly"
            self.assertEqual(metadata["temporal_resolution"], "monthly")
            # Exigencia 4: serie de 12 meses ordenada
            self.assertEqual(len(data["timeseries"]), 12)
            self.assertEqual(data["timeseries"][0]["date"], "2023-01-01")
            self.assertEqual(data["timeseries"][11]["date"], "2023-12-01")


if __name__ == "__main__":
    unittest.main()
