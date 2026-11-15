import json
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
from app.core.cache import (
    DEFAULT_PROCESSING_VERSION,
    DEFAULT_PRODUCT_VERSION,
    get_cache_dir,
    invalidate_cache,
    load_from_cache,
    make_cache_key,
    save_to_cache,
)
from app.models.exploration import ExplorationRequest
from app.models.geojson import GeoJSONPolygon
from app.services.exploration_service import get_catalog, run_exploration
from app.services.gpm_imerg import GPMIMERGResult, MonthlyPrecipitation


class Issue19ProvenanceCacheCatalogTests(unittest.TestCase):
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
        self.start = date(2023, 1, 1)
        self.end = date(2023, 12, 31)

        dates = pd.date_range("2023-01-01", periods=12, freq="MS")
        self.df = pd.DataFrame(
            {
                "precipitation_mm": [120.0 + i * 5 for i in range(12)],
                "coverage_fraction": [1.0] * 12,
                "quality_flag": ["ok"] * 12,
            },
            index=dates,
        )
        self.df.index.name = "month"

        self.mock_harmony_result = GPMIMERGResult(
            dataset="GPM_3IMERGM.07",
            version="07",
            region=self.geom,
            source_units="mm/hr",
            output_units="mm/month",
            unit_conversion="Multiplicación por horas del mes calendario según año bisiesto",
            spatial_resolution_degrees=0.1,
            granule_ids=tuple(f"GPM_3IMERGM_2023_{m:02d}" for m in range(1, 13)),
            weighting_method="Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)",
            monthly_values=tuple(
                MonthlyPrecipitation(
                    month=dates[i].date(),
                    value=120.0 + i * 5,
                    coverage_fraction=1.0,
                )
                for i in range(12)
            ),
        )

    def test_cache_key_includes_product_and_processing_versions(self) -> None:
        """Criterio 2: La clave de caché versiona explícitamente producto, procesamiento, datos y geometría."""
        key = make_cache_key(
            "precipitation",
            "costa-rica-continental",
            self.geom,
            self.start,
            self.end,
            product_version="v07",
            processing_version="p1",
        )
        self.assertIn("precipitation_v07_p1_costa-rica-continental_", key)
        self.assertTrue(key.endswith("2023-01-01_2023-12-31.json"))

    def test_fresh_and_cached_responses_preserve_identical_provenance(self) -> None:
        """Criterios 1 y 4: Respuesta fresca y respuesta cacheada conservan la misma procedencia

        completa y verificable (origen, versión, DOI, gránulos, método).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.core.cache.get_cache_dir", return_value=Path(tmpdir)):
                mock_connector = MagicMock()
                mock_connector.fetch_monthly_precipitation.return_value = self.mock_harmony_result

                req = ExplorationRequest(
                    region_id="cuenca-canal-panama",
                    variable_id="precipitation",
                    start_date=self.start,
                    end_date=self.end,
                )

                # 1. Ejecución fresca (origen NASA Harmony)
                with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}):
                    fresh_resp = run_exploration(req, connector=mock_connector)

                fresh_meta = fresh_resp.metadata
                self.assertEqual(fresh_meta.effective_origin, "NASA Harmony")
                self.assertEqual(fresh_meta.source, "NASA GES DISC mediante CMR y Harmony")
                self.assertEqual(fresh_meta.product_version, "07")
                self.assertEqual(fresh_meta.processing_version, "1.0")
                self.assertEqual(fresh_meta.doi_or_link, "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07")
                self.assertEqual(len(fresh_meta.source_granule_ids), 12)
                self.assertIsNotNone(fresh_meta.data_accessed_at)
                self.assertIsNotNone(fresh_meta.quality_method)

                # 2. Segunda ejecución: Cache hit en modo auto
                mock_connector.fetch_monthly_precipitation.reset_mock()
                with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}):
                    cached_resp = run_exploration(req, connector=mock_connector)

                mock_connector.fetch_monthly_precipitation.assert_not_called()
                cached_meta = cached_resp.metadata

                # Ambos conservan exactamente la misma procedencia
                self.assertEqual(cached_meta.effective_origin, fresh_meta.effective_origin)
                self.assertEqual(cached_meta.source, fresh_meta.source)
                self.assertEqual(cached_meta.product_version, fresh_meta.product_version)
                self.assertEqual(cached_meta.processing_version, fresh_meta.processing_version)
                self.assertEqual(cached_meta.doi_or_link, fresh_meta.doi_or_link)
                self.assertEqual(cached_meta.source_granule_ids, fresh_meta.source_granule_ids)
                self.assertEqual(cached_meta.source_units, fresh_meta.source_units)
                self.assertEqual(cached_meta.unit_conversion, fresh_meta.unit_conversion)
                self.assertEqual(cached_meta.weighting_method, fresh_meta.weighting_method)

    def test_harmony_is_never_labeled_as_giovanni(self) -> None:
        """Criterio 4: Comprobar que una extracción satelital directa o vía Harmony

        NUNCA se etiqueta como Giovanni.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.core.cache.get_cache_dir", return_value=Path(tmpdir)):
                mock_connector = MagicMock()
                mock_connector.fetch_monthly_precipitation.return_value = self.mock_harmony_result

                req = ExplorationRequest(
                    region_id="cuenca-canal-panama",
                    variable_id="precipitation",
                    start_date=self.start,
                    end_date=self.end,
                )
                with patch.dict("os.environ", {"IYOK_DATA_SOURCE": "auto"}):
                    resp = run_exploration(req, connector=mock_connector)

                # Verificar que NO se menciona Giovanni en origen ni en fuente
                self.assertNotIn("giovanni", resp.metadata.effective_origin.lower())
                self.assertNotIn("giovanni", resp.metadata.source.lower())
                self.assertIn("harmony", resp.metadata.effective_origin.lower())

    def test_incomplete_cache_is_purged_and_recovers_gracefully(self) -> None:
        """Criterio 2: Recuperación ante caché incompleta. Si a un archivo de caché le faltan

        meses esperados, load_from_cache lo descarta, lo elimina y devuelve None para permitir
        reingestión fresca.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch("app.core.cache.get_cache_dir", return_value=tmp_path):
                # Guardar solo 6 meses de los 12 esperados
                partial_df = self.df.iloc[:6]
                save_to_cache(
                    "precipitation",
                    "cr",
                    self.geom,
                    self.start,
                    self.end,
                    partial_df,
                    provenance={"effective_origin": "NASA Harmony"},
                )

                cache_key = make_cache_key("precipitation", "cr", self.geom, self.start, self.end)
                cache_file = tmp_path / cache_key
                self.assertTrue(cache_file.exists())

                # Intentar cargar para el rango completo de 12 meses
                loaded = load_from_cache("precipitation", "cr", self.geom, self.start, self.end)
                self.assertIsNone(loaded)
                # El archivo incompleto debe haber sido purgado
                self.assertFalse(cache_file.exists())

    def test_corrupt_json_cache_is_purged_and_returns_none(self) -> None:
        """Criterio 2: Ante corrupción de archivo JSON (parse error), el archivo se purga y devuelve None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch("app.core.cache.get_cache_dir", return_value=tmp_path):
                cache_key = make_cache_key("precipitation", "cr", self.geom, self.start, self.end)
                cache_file = tmp_path / cache_key
                cache_file.write_text("{ corrupt json data ::: [}", encoding="utf-8")
                self.assertTrue(cache_file.exists())

                loaded = load_from_cache("precipitation", "cr", self.geom, self.start, self.end)
                self.assertIsNone(loaded)
                self.assertFalse(cache_file.exists())

    def test_explicit_cache_invalidation_purges_file(self) -> None:
        """Criterio 2: Invalida explícitamente y purga una clave de caché."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch("app.core.cache.get_cache_dir", return_value=tmp_path):
                save_to_cache(
                    "precipitation",
                    "cr",
                    self.geom,
                    self.start,
                    self.end,
                    self.df,
                )
                cache_key = make_cache_key("precipitation", "cr", self.geom, self.start, self.end)
                cache_file = tmp_path / cache_key
                self.assertTrue(cache_file.exists())

                result = invalidate_cache("precipitation", "cr", self.geom, self.start, self.end)
                self.assertTrue(result)
                self.assertFalse(cache_file.exists())

    def test_catalog_distinguishes_declared_verified_and_source_unavailable(self) -> None:
        """Criterio 3: El catálogo distingue intervalo declarado, disponibilidad verificada,

        huecos y estados cuando la fuente no está disponible de inmediato.
        """
        # Sin token Earthdata en el entorno
        with patch.dict("os.environ", {"EARTHDATA_TOKEN": ""}):
            catalog = get_catalog()

            # Variable contiene intervalos y DOI
            var = catalog.variables[0]
            self.assertIsNotNone(var.declared_interval)
            self.assertIsNotNone(var.verified_interval)
            self.assertEqual(var.known_gaps, [])
            self.assertEqual(var.doi_or_link, "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07")
            self.assertEqual(var.source_status, "verified")

            # Costa Rica Continental es verificada e inmediata
            cr_comb = next(c for c in catalog.combinations if c.region_id == "costa-rica-continental")
            self.assertTrue(cr_comb.is_ready_for_exploration)
            self.assertEqual(cr_comb.source_status, "verified")
            self.assertIsNotNone(cr_comb.declared_interval)
            self.assertIsNotNone(cr_comb.verified_interval)

            # Panamá sin token está marcada como source_unavailable y no lista inmediatamente
            panama_comb = next(c for c in catalog.combinations if c.region_id == "cuenca-canal-panama")
            self.assertFalse(panama_comb.is_ready_for_exploration)
            self.assertEqual(panama_comb.source_status, "source_unavailable")
            self.assertIsNone(panama_comb.verified_interval)
            self.assertIn("requiere configurar EARTHDATA_TOKEN", panama_comb.notes)

        # Con token Earthdata configurado
        with patch.dict("os.environ", {"EARTHDATA_TOKEN": "valid_token"}):
            catalog_with_token = get_catalog()
            panama_token_comb = next(
                c for c in catalog_with_token.combinations if c.region_id == "cuenca-canal-panama"
            )
            self.assertTrue(panama_token_comb.is_ready_for_exploration)
            self.assertEqual(panama_token_comb.source_status, "on_demand")
            self.assertIsNotNone(panama_token_comb.verified_interval)


if __name__ == "__main__":
    unittest.main()
