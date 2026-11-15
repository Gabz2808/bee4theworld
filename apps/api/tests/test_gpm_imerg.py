import tempfile
import unittest
from unittest.mock import patch
from datetime import date
from pathlib import Path

import httpx
import cftime
import numpy as np
import pandas as pd
import xarray as xr
from pydantic import ValidationError
from shapely.geometry import Polygon

from app.models.geojson import GeoJSONPolygon
from app.services.gpm_imerg import (
    DataUnavailableError,
    GPMIMERGConnector,
    _aggregate_dataset,
    _area_weights,
)


def _region(coordinates: list[list[list[float]]]) -> GeoJSONPolygon:
    return GeoJSONPolygon(type="Polygon", coordinates=coordinates)


def _sample_region() -> GeoJSONPolygon:
    return _region(
        [[
            [-85.1, 9.9],
            [-84.9, 9.9],
            [-84.9, 10.1],
            [-85.1, 10.1],
            [-85.1, 9.9],
        ]]
    )


def _netcdf(path: Path, units: str, values: np.ndarray | None = None) -> Path:
    if values is None:
        values = np.ones((1, 2, 2), dtype=float)
    dataset = xr.Dataset(
        {
            "precipitation": (
                ("time", "lat", "lon"),
                values,
                {"units": units},
            )
        },
        coords={
            "time": pd.date_range("2024-02-01", periods=1),
            "lat": [9.95, 10.05],
            "lon": [-85.05, -84.95],
        },
    )
    dataset.to_netcdf(path, engine="netcdf4")
    return path


def _netcdf_with_group(path: Path, units: str = "mm/hr") -> Path:
    import netCDF4

    nc = netCDF4.Dataset(str(path), "w", format="NETCDF4")
    grid_grp = nc.createGroup("Grid")
    grid_grp.createDimension("time", 1)
    grid_grp.createDimension("lat", 2)
    grid_grp.createDimension("lon", 2)

    t_var = grid_grp.createVariable("time", "f8", ("time",))
    t_var.units = "days since 2024-02-01 00:00:00"
    t_var.calendar = "julian"
    t_var[:] = [0]

    lat_var = grid_grp.createVariable("lat", "f4", ("lat",))
    lat_var.units = "degrees_north"
    lat_var[:] = [9.95, 10.05]

    lon_var = grid_grp.createVariable("lon", "f4", ("lon",))
    lon_var.units = "degrees_east"
    lon_var[:] = [-85.05, -84.95]

    precip_var = grid_grp.createVariable("precipitation", "f4", ("time", "lat", "lon"))
    precip_var.units = units
    precip_var[:] = np.ones((1, 2, 2)) * 2.5
    nc.close()
    return path


class CompletedDownload:
    def __init__(self, path: Path) -> None:
        self.path = path

    def result(self) -> str:
        return str(self.path)


class FakeHarmonyClient:
    def __init__(self, source_path: Path) -> None:
        self.source_path = source_path
        self.request = None

    def submit(self, request: object) -> str:
        self.request = request
        return "mock-job"

    def download_all(
        self,
        job_id: str,
        directory: str,
        overwrite: bool,
    ) -> list[CompletedDownload]:
        target = Path(directory) / "monthly.nc"
        target.write_bytes(self.source_path.read_bytes())
        return [CompletedDownload(target)]


class GPMIMERGTests(unittest.TestCase):
    def test_area_weights_include_partial_boundary_cells(self) -> None:
        region = _region(
            [[
                [-85.05, 9.95],
                [-84.9, 9.95],
                [-84.9, 10.05],
                [-85.05, 10.05],
                [-85.05, 9.95],
            ]]
        )
        geometry = Polygon(region.coordinates[0])
        weights, region_area = _area_weights(
            geometry,
            np.array([10.0]),
            np.array([-85.0, -84.9]),
        )

        self.assertAlmostEqual(weights[0, 0] / weights[0, 1], 2.0, places=5)
        self.assertAlmostEqual(float(weights.sum()) / region_area, 1.0, places=5)

    def test_area_weights_account_for_latitude(self) -> None:
        geometry = Polygon(
            [
                (-85.05, 9.95),
                (-84.95, 9.95),
                (-84.95, 20.05),
                (-85.05, 20.05),
                (-85.05, 9.95),
            ]
        )
        weights, _ = _area_weights(
            geometry,
            np.array([10.0, 20.0]),
            np.array([-85.0]),
        )

        self.assertGreater(weights[0, 0], weights[1, 0])

    def test_area_mean_and_coverage_are_returned_for_each_month(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = _netcdf(Path(directory) / "monthly.nc", "mm/hr")
            dataset = xr.open_dataset(path, engine="netcdf4")
            try:
                units, records = _aggregate_dataset(
                    dataset,
                    Polygon(_sample_region().coordinates[0]),
                    (date(2024, 2, 1),),
                )
            finally:
                dataset.close()

        self.assertEqual(units, "mm/hr")
        self.assertEqual(records[0].value, 1)
        self.assertAlmostEqual(records[0].coverage_fraction, 1.0, places=5)

    def test_monthly_coverage_reflects_missing_cells(self) -> None:
        values = np.array([[[1.0, np.nan], [1.0, 1.0]]])
        with tempfile.TemporaryDirectory() as directory:
            path = _netcdf(Path(directory) / "monthly.nc", "mm", values)
            dataset = xr.open_dataset(path, engine="netcdf4")
            try:
                _, records = _aggregate_dataset(
                    dataset,
                    Polygon(_sample_region().coordinates[0]),
                    (date(2024, 2, 1),),
                )
            finally:
                dataset.close()

        self.assertGreater(records[0].coverage_fraction, 0)
        self.assertLess(records[0].coverage_fraction, 1)

    def test_connector_checks_cmr_then_requests_the_selected_granules(self) -> None:
        granule = {
            "id": "G123-GES_DISC",
            "collection_concept_id": "C123-GES_DISC",
            "time_start": "2024-02-01T00:00:00.000Z",
        }
        cmr_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"feed": {"entry": [granule]}},
                )
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source = _netcdf(Path(directory) / "source.nc", "mm")
            harmony = FakeHarmonyClient(source)
            connector = GPMIMERGConnector(
                harmony_client=harmony,
                cmr_client=cmr_client,
            )
            result = connector.fetch_monthly_precipitation(
                _sample_region(),
                date(2024, 2, 1),
                date(2024, 2, 29),
            )
        cmr_client.close()

        self.assertEqual(result.dataset, "GPM_3IMERGM.07")
        self.assertEqual(result.granule_ids, ("G123-GES_DISC",))
        self.assertEqual(result.monthly_values[0].value, 1)
        self.assertEqual(result.region, _sample_region())
        self.assertEqual(harmony.request.variables, ["all"])

    def test_connector_supports_netcdf_group_grid_and_cftime(self) -> None:
        granule = {
            "id": "G123-GES_DISC",
            "collection_concept_id": "C123-GES_DISC",
            "time_start": "2024-02-01T00:00:00.000Z",
        }
        cmr_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200,
                    json={"feed": {"entry": [granule]}},
                )
            )
        )
        with tempfile.TemporaryDirectory() as directory:
            source = _netcdf_with_group(Path(directory) / "source_grouped.nc")
            harmony = FakeHarmonyClient(source)
            connector = GPMIMERGConnector(
                harmony_client=harmony,
                cmr_client=cmr_client,
            )
            result = connector.fetch_monthly_precipitation(
                _sample_region(),
                date(2024, 2, 1),
                date(2024, 2, 29),
            )
        cmr_client.close()

        self.assertEqual(result.dataset, "GPM_3IMERGM.07")
        self.assertEqual(result.granule_ids, ("G123-GES_DISC",))
        self.assertAlmostEqual(result.monthly_values[0].value, 2.5, places=4)
        self.assertEqual(result.monthly_values[0].month, date(2024, 2, 1))
    def test_reads_grid_group_and_julian_calendar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grid.nc"
            dataset = xr.Dataset(
                {"precipitation": (("time", "lon", "lat"), np.ones((1, 2, 2)), {"units": "mm/hr"})},
                coords={"time": [cftime.DatetimeJulian(2024, 2, 1)], "lat": [9.95, 10.05], "lon": [-85.05, -84.95]},
            )
            dataset.to_netcdf(path, engine="netcdf4", group="Grid")
            result = GPMIMERGConnector._read_result(
                [path], _sample_region(), Polygon(_sample_region().coordinates[0]),
                (date(2024, 2, 1),),
                [{"id": "G123-GES_DISC", "collection_concept_id": "C123-GES_DISC", "time_start": "2024-02-01T00:00:00Z"}],
            )
        self.assertEqual(result.source_units, "mm/hr")
        self.assertEqual(result.monthly_values[0].month, date(2024, 2, 1))
        self.assertAlmostEqual(result.monthly_values[0].coverage_fraction, 1.0, places=5)

    def test_connector_fails_when_cmr_has_no_monthly_granule(self) -> None:
        cmr_client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"feed": {"entry": []}})
            )
        )
        connector = GPMIMERGConnector(cmr_client=cmr_client)
        try:
            with patch.dict("os.environ", {"EARTHDATA_TOKEN": "test-token"}), self.assertRaises(DataUnavailableError):
                connector.fetch_monthly_precipitation(
                    _sample_region(),
                    date(2024, 2, 1),
                    date(2024, 2, 29),
                )
        finally:
            cmr_client.close()

    def test_connector_rejects_partial_month_ranges(self) -> None:
        with self.assertRaises(ValueError):
            GPMIMERGConnector().fetch_monthly_precipitation(
                _sample_region(),
                date(2024, 2, 2),
                date(2024, 2, 29),
            )

    def test_geojson_model_rejects_nonclosed_polygon(self) -> None:
        with self.assertRaises(ValidationError):
            _region(
                [[
                    [-85.1, 9.9],
                    [-84.9, 9.9],
                    [-84.9, 10.1],
                    [-85.1, 10.1],
                ]]
            )


if __name__ == "__main__":
    unittest.main()
