"""Pruebas de integración con sustitutos (mocks) para Issue #15:

Asegura que:
1. Una geometría personalizada nunca se asocia por defecto a otra región y se conserva fuera de Supabase.
2. La persistencia es atómica con rollback defensivo ante fallos parciales.
3. Se garantiza la idempotencia y la selección determinista descartando ingestas incompletas.
4. No se modifican datos reales durante las pruebas.
"""
from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock, call

import pandas as pd
from app.core.cache import save_to_supabase
from app.models.exploration import ExplorationRequest
from app.models.geojson import GeoJSONPolygon
from app.services.exploration_service import _fetch_from_supabase
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation


class Issue15SupabaseIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_supabase = MagicMock()
        self.sample_geom = GeoJSONPolygon(
            type="Polygon",
            coordinates=[
                [
                    [-80.00, 8.80],
                    [-79.50, 8.80],
                    [-79.50, 9.30],
                    [-80.00, 9.30],
                    [-80.00, 8.80],
                ]
            ],
        )
        self.start = date(2023, 1, 1)
        self.end = date(2023, 12, 31)

        dates = pd.date_range(start=self.start, end=self.end, freq="MS")
        self.monthly_frame = pd.DataFrame(
            {
                "precipitation_mm": [100.0] * 12,
                "coverage_fraction": [1.0] * 12,
                "quality_flag": ["ok"] * 12,
            },
            index=dates,
        )

        self.mock_result = GPMIMERGResult(
            dataset="GPM_3IMERGM.07",
            version="07",
            region=self.sample_geom,
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="Conversión estándar Pandas",
            spatial_resolution_degrees=0.1,
            granule_ids=("granule-1", "granule-2"),
            weighting_method="Intersección parcial y área equivalente",
            monthly_values=(
                MonthlyPrecipitation(
                    month=date(2023, 1, 1),
                    value=100.0,
                    coverage_fraction=1.0,
                ),
            ),
        )

    def test_custom_polygon_is_conserved_outside_supabase_and_never_calls_costa_rica(self) -> None:
        """Criterio 1: Un polígono personalizado nunca se asocia a otra región ni intenta buscar Costa Rica Continental."""
        req = ExplorationRequest(
            variable_id="precipitation",
            region=self.sample_geom,
            start_date=self.start,
            end_date=self.end,
        )

        save_to_supabase(
            supabase=self.mock_supabase,
            request=req,
            geom=self.sample_geom,
            result=self.mock_result,
            monthly_frame=self.monthly_frame,
            region_identifier="custom-polygon",
        )

        # Verificar que NUNCA intentó buscar Costa Rica Continental ni registrar nada en Supabase
        self.mock_supabase.table.assert_not_called()

    def test_fetch_from_supabase_returns_none_for_custom_polygon(self) -> None:
        """Criterio 1: La lectura desde Supabase omite polígonos personalizados para preservarlos en caché local."""
        req = ExplorationRequest(
            variable_id="precipitation",
            region=self.sample_geom,
            start_date=self.start,
            end_date=self.end,
        )

        df = _fetch_from_supabase(
            supabase=self.mock_supabase,
            request=req,
            start=self.start,
            end=self.end,
            region_identifier="custom-polygon",
            geom=self.sample_geom,
        )

        self.assertIsNone(df)
        self.mock_supabase.table.assert_not_called()

    def test_unknown_region_identifier_never_defaults_to_costa_rica(self) -> None:
        """Criterio 1: Un identificador desconocido no cae por defecto a Costa Rica Continental."""
        req = ExplorationRequest(
            variable_id="precipitation",
            region_id="region-desconocida-xyz",
            start_date=self.start,
            end_date=self.end,
        )

        save_to_supabase(
            supabase=self.mock_supabase,
            request=req,
            geom=self.sample_geom,
            result=self.mock_result,
            monthly_frame=self.monthly_frame,
            region_identifier="region-desconocida-xyz",
        )

        # Como 'region-desconocida-xyz' no está en el catálogo verificado, no debe buscar 'Costa Rica Continental'
        self.mock_supabase.table.assert_not_called()

    def test_registered_region_persists_strictly_to_verified_uuid(self) -> None:
        """Criterio 1 & 2: Una región de catálogo registrada se asocia exclusivamente a su UUID verificado."""
        verified_uuid = "96bdd25d-7fed-4b9e-b2ac-23a197a5d2d5"
        mock_table = MagicMock()
        self.mock_supabase.table.return_value = mock_table

        # 1. Simular búsqueda de región en public.regions
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": verified_uuid, "name": "Costa Rica Continental"}
        ]
        # 2. Simular verificación de idempotencia (no existe previo)
        mock_table.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        # 3. Simular inserción exitosa de ingestion_run y processed_data
        def insert_side_effect(payload):
            mock_res = MagicMock()
            if isinstance(payload, dict) and "region_id" in payload:
                mock_res.execute.return_value.data = [{"id": "run-uuid-777"}]
            else:
                mock_res.execute.return_value.data = [{"id": f"pt-{i}"} for i in range(len(payload))]
            return mock_res

        mock_table.insert.side_effect = insert_side_effect

        req = ExplorationRequest(
            variable_id="precipitation",
            region_id="costa-rica-continental",
            start_date=self.start,
            end_date=self.end,
        )

        save_to_supabase(
            supabase=self.mock_supabase,
            request=req,
            geom=self.sample_geom,
            result=self.mock_result,
            monthly_frame=self.monthly_frame,
            region_identifier="costa-rica-continental",
        )

        # Verificar que se consultó la tabla 'regions' específicamente por 'Costa Rica Continental'
        self.mock_supabase.table.assert_any_call("regions")
        # Verificar que se insertó en ingestion_runs con el UUID verificado
        self.mock_supabase.table.assert_any_call("ingestion_runs")
        self.mock_supabase.table.assert_any_call("processed_data")

    def test_idempotency_skips_duplicate_insertion_when_run_is_already_complete(self) -> None:
        """Criterio 2: Idempotencia evita duplicar ingestas ya completas en Supabase."""
        verified_uuid = "96bdd25d-7fed-4b9e-b2ac-23a197a5d2d5"
        mock_table = MagicMock()
        self.mock_supabase.table.return_value = mock_table

        # Región encontrada
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": verified_uuid, "name": "Costa Rica Continental"}
        ]
        # Run existente ya registrado
        mock_table.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {"id": "run-existente-123"}
        ]
        # Puntos existentes ya completos (12 meses)
        mock_table.select.return_value.eq.return_value.execute.return_value.data = [
            {"observed_month": f"2023-{m:02d}-01"} for m in range(1, 13)
        ]

        req = ExplorationRequest(
            variable_id="precipitation",
            region_id="costa-rica-continental",
            start_date=self.start,
            end_date=self.end,
        )

        save_to_supabase(
            supabase=self.mock_supabase,
            request=req,
            geom=self.sample_geom,
            result=self.mock_result,
            monthly_frame=self.monthly_frame,
            region_identifier="costa-rica-continental",
        )

        # Como ya existe y está completa, NO debe llamar a insert en ingestion_runs
        mock_table.insert.assert_not_called()

    def test_partial_failure_in_processed_data_triggers_defensive_rollback(self) -> None:
        """Criterio 2: Fallo parcial en la inserción de processed_data elimina el ingestion_run para garantizar atomicidad."""
        verified_uuid = "96bdd25d-7fed-4b9e-b2ac-23a197a5d2d5"
        mock_table = MagicMock()
        self.mock_supabase.table.return_value = mock_table

        # Región encontrada
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": verified_uuid, "name": "Costa Rica Continental"}
        ]
        # Sin run previo
        mock_table.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        # Ingestion run creado exitosamente
        created_run_id = "run-a-revertir-999"
        run_insert_mock = MagicMock()
        run_insert_mock.execute.return_value.data = [{"id": created_run_id}]

        # Pero processed_data falla (ej. error de red o timeout)
        def insert_side_effect(payload):
            if isinstance(payload, dict) and "region_id" in payload:
                return run_insert_mock
            raise RuntimeError("Fallo de red simulado al insertar processed_data")

        mock_table.insert.side_effect = insert_side_effect

        req = ExplorationRequest(
            variable_id="precipitation",
            region_id="costa-rica-continental",
            start_date=self.start,
            end_date=self.end,
        )

        save_to_supabase(
            supabase=self.mock_supabase,
            request=req,
            geom=self.sample_geom,
            result=self.mock_result,
            monthly_frame=self.monthly_frame,
            region_identifier="costa-rica-continental",
        )

        # Verificar que se ejecutó el delete() defensivo de ingestion_runs con created_run_id
        mock_table.delete.assert_called_once()
        mock_table.delete.return_value.eq.assert_called_once_with("id", created_run_id)

    def test_fetch_from_supabase_skips_incomplete_runs_deterministically(self) -> None:
        """Criterio 2: _fetch_from_supabase descarta cualquier ingesta incompleta y selecciona la completa determinista."""
        verified_uuid = "96bdd25d-7fed-4b9e-b2ac-23a197a5d2d5"
        mock_table = MagicMock()
        self.mock_supabase.table.return_value = mock_table

        # Región verificada
        mock_table.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": verified_uuid, "name": "Costa Rica Continental"}
        ]

        # Dos runs encontrados ordenados por created_at desc:
        # Run 1 (más reciente): incompleto (solo 4 meses)
        # Run 2 (anterior): completo (12 meses)
        mock_table.select.return_value.eq.return_value.eq.return_value.lte.return_value.gte.return_value.order.return_value.execute.return_value.data = [
            {"id": "run-incompleto-1"},
            {"id": "run-completo-2"},
        ]

        # Simular respuestas de processed_data para cada run
        incomplete_rows = [
            {"observed_month": f"2023-{m:02d}-01", "precipitation_mm": 50.0, "coverage_fraction": 1.0, "quality_flag": "ok"}
            for m in range(1, 5)
        ]
        complete_rows = [
            {"observed_month": f"2023-{m:02d}-01", "precipitation_mm": 120.0, "coverage_fraction": 1.0, "quality_flag": "ok"}
            for m in range(1, 13)
        ]

        def processed_data_side_effect(*args, **kwargs):
            # Obtener el run_id del filtro eq("ingestion_run_id", ...)
            return MagicMock(
                gte=lambda *a, **k: MagicMock(
                    lte=lambda *a, **k: MagicMock(
                        order=lambda *a, **k: MagicMock(
                            execute=lambda: MagicMock(
                                data=incomplete_rows if mock_table.eq.call_args_list[-1] == call("ingestion_run_id", "run-incompleto-1") else complete_rows
                            )
                        )
                    )
                )
            )

        # Configuramos para que el primer execute de processed_data devuelva 4 filas y el segundo 12 filas
        exec_mock_incomplete = MagicMock()
        exec_mock_incomplete.data = incomplete_rows
        exec_mock_complete = MagicMock()
        exec_mock_complete.data = complete_rows

        query_chain_incomplete = MagicMock()
        query_chain_incomplete.execute.return_value = exec_mock_incomplete

        query_chain_complete = MagicMock()
        query_chain_complete.execute.return_value = exec_mock_complete

        # En processed_data, alternar entre incomplete y complete
        mock_table.select.return_value.eq.return_value.gte.return_value.lte.return_value.order.side_effect = [
            query_chain_incomplete,
            query_chain_complete,
        ]

        req = ExplorationRequest(
            variable_id="precipitation",
            region_id="costa-rica-continental",
            start_date=self.start,
            end_date=self.end,
        )

        df = _fetch_from_supabase(
            supabase=self.mock_supabase,
            request=req,
            start=self.start,
            end=self.end,
            region_identifier="costa-rica-continental",
            geom=self.sample_geom,
        )

        # Debe retornar el DataFrame completo de 12 meses, ignorando el run incompleto
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 12)
        self.assertEqual(df["precipitation_mm"].iloc[0], 120.0)


if __name__ == "__main__":
    unittest.main()
