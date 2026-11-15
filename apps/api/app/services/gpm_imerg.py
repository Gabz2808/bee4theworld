from __future__ import annotations

import calendar
import logging
import os
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import TypedDict

import httpx
import numpy as np
import pandas as pd
import xarray as xr
from harmony import BBox, Client, Collection, Request
from pyproj import Transformer
from shapely import transform as transform_geometry
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.prepared import prep
from shapely.validation import explain_validity

from app.models.geojson import GeoJSONMultiPolygon, GeoJSONPolygon

AnalysisRegion = GeoJSONPolygon | GeoJSONMultiPolygon
AnalysisGeometry = Polygon | MultiPolygon

logger = logging.getLogger(__name__)

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
CMR_SHORT_NAME = "GPM_3IMERGM"
CMR_VERSION = "07"
HARMONY_VARIABLE = "Grid/precipitation"
PRECIPITATION_VARIABLE = "precipitation"
GRID_RESOLUTION_DEGREES = 0.1
EQUAL_AREA_CRS = "EPSG:6933"


class CMRGranule(TypedDict):
    id: str
    collection_concept_id: str
    time_start: str


class GPMIMERGError(RuntimeError):
    pass


class DataUnavailableError(GPMIMERGError):
    pass


class DataIntegrityError(GPMIMERGError):
    pass


class EarthdataAuthenticationRequired(GPMIMERGError):
    """No hay token explícito para la consulta directa a NASA."""


@dataclass(frozen=True)
class MonthlyPrecipitation:
    month: date
    value: float | None
    coverage_fraction: float


@dataclass(frozen=True)
class GPMIMERGResult:
    dataset: str
    version: str
    region: AnalysisRegion
    source_units: str
    output_units: str
    unit_conversion: str
    spatial_resolution_degrees: float
    granule_ids: tuple[str, ...]
    weighting_method: str
    monthly_values: tuple[MonthlyPrecipitation, ...]


class GPMIMERGConnector:
    def __init__(
        self,
        *,
        harmony_client: Client | None = None,
        cmr_client: httpx.Client | None = None,
    ) -> None:
        self._harmony_client = harmony_client
        self._cmr_client = cmr_client

    def fetch_monthly_precipitation(
        self,
        region: AnalysisRegion,
        start: date,
        end: date,
    ) -> GPMIMERGResult:
        months = _requested_months(start, end)
        geometry = _polygon_from_geojson(region)
        if self._harmony_client is None and not os.environ.get("EARTHDATA_TOKEN", "").strip():
            raise EarthdataAuthenticationRequired("Configure EARTHDATA_TOKEN en el entorno de la API.")
        granules = self._search_granules(start, end, months)
        collection_ids = {granule["collection_concept_id"] for granule in granules}
        if len(collection_ids) != 1:
            raise DataIntegrityError("CMR devolvió granules de distintas colecciones")

        request = Request(
            collection=Collection(id=collection_ids.pop()),
            spatial=_bounding_box(geometry),
            temporal={
                "start": datetime.combine(start, time.min, tzinfo=UTC),
                "stop": datetime.combine(end, time.max, tzinfo=UTC),
            },
            granule_id=[granule["id"] for granule in granules],
            format="application/x-netcdf4",
            ignore_errors=False,
            skip_preview=True,
        )

        client = self._get_harmony_client()
        job_id = client.submit(request)
        logger.info("Trabajo Harmony iniciado: %s", job_id)
        with tempfile.TemporaryDirectory(prefix="iyok-imerg-") as temp_dir:
            futures = client.download_all(
                job_id,
                directory=temp_dir,
                overwrite=True,
            )
            paths = [Path(future.result()) for future in futures]
            if not paths:
                raise DataUnavailableError("Harmony no devolvió archivos para la consulta")
            return self._read_result(paths, region, geometry, months, granules)

    def _get_harmony_client(self) -> Client:
        if self._harmony_client is None:
            token = os.environ.get("EARTHDATA_TOKEN")
            self._harmony_client = Client(token=token) if token else Client()
        return self._harmony_client

    def _search_granules(
        self,
        start: date,
        end: date,
        expected_months: tuple[date, ...],
    ) -> list[CMRGranule]:
        params = {
            "short_name": CMR_SHORT_NAME,
            "version": CMR_VERSION,
            "temporal": (
                f"{start.isoformat()}T00:00:00Z,"
                f"{end.isoformat()}T23:59:59Z"
            ),
            "page_size": 2000,
        }
        client = self._cmr_client or httpx.Client(timeout=30.0)
        should_close = self._cmr_client is None
        try:
            response = client.get(CMR_GRANULES_URL, params=params)
            response.raise_for_status()
            entries = response.json().get("feed", {}).get("entry", [])
        finally:
            if should_close:
                client.close()

        expected = set(expected_months)
        found: dict[date, CMRGranule] = {}
        for entry in entries:
            if not all(
                field in entry
                for field in ("id", "collection_concept_id", "time_start")
            ):
                raise DataIntegrityError("CMR devolvió un granule sin metadatos requeridos")
            granule_start = pd.Timestamp(entry["time_start"]).date()
            month = granule_start.replace(day=1)
            if month not in expected:
                continue
            if month in found:
                raise DataIntegrityError(
                    f"CMR devolvió más de un granule para {month:%Y-%m}"
                )
            found[month] = entry

        missing = sorted(expected - found.keys())
        if missing:
            missing_months = ", ".join(month.strftime("%Y-%m") for month in missing)
            raise DataUnavailableError(
                f"IMERG Final V07 no tiene cobertura CMR para: {missing_months}"
            )
        return [found[month] for month in expected_months]

    @staticmethod
    def _read_result(
        paths: list[Path],
        region: AnalysisRegion,
        geometry: AnalysisGeometry,
        expected_months: tuple[date, ...],
        granules: list[CMRGranule],
    ) -> GPMIMERGResult:
        with ExitStack() as stack:
            datasets = []
            for path in paths:
                ds = None
                try:
                    candidate = stack.enter_context(
                        xr.open_dataset(path, group="Grid", engine="netcdf4")
                    )
                    if candidate.data_vars:
                        ds = candidate
                except Exception:
                    logger.debug("No se pudo abrir el grupo Grid; se intentar? la ra?z.", exc_info=True)
                if ds is None:
                    ds = stack.enter_context(
                        xr.open_dataset(path, engine="netcdf4")
                    )
                datasets.append(ds)
            dataset = (
                datasets[0]
                if len(datasets) == 1
                else xr.concat(datasets, dim="time", data_vars="minimal")
            )
            result = _aggregate_dataset(dataset, geometry, expected_months)

        return GPMIMERGResult(
            dataset=f"{CMR_SHORT_NAME}.{CMR_VERSION}",
            version=CMR_VERSION,
            region=region,
            source_units=result[0],
            output_units="mm/month",
            spatial_resolution_degrees=GRID_RESOLUTION_DEGREES,
            granule_ids=tuple(granule["id"] for granule in granules),
            weighting_method=(
                "Intersección parcial de celdas y área en proyección equivalente "
                f"en {EQUAL_AREA_CRS}"
            ),
            unit_conversion=(
                "La conversión a mm/month se aplica en Pandas usando la duración "
                "real de cada mes."
            ),
            monthly_values=result[1],
        )


def _requested_months(start: date, end: date) -> tuple[date, ...]:
    if start.day != 1:
        raise ValueError("El inicio debe ser el primer día de un mes completo")
    if end.day != calendar.monthrange(end.year, end.month)[1]:
        raise ValueError("El final debe ser el último día de un mes completo")
    if end < start:
        raise ValueError("La fecha final debe ser igual o posterior a la inicial")

    months: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(date(year, month, 1))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return tuple(months)


def _polygon_from_geojson(region: AnalysisRegion) -> AnalysisGeometry:
    geometry = shape(region.model_dump(mode="json"))
    if geometry.is_empty or not geometry.is_valid:
        raise ValueError(f"Polígono inválido: {explain_validity(geometry)}")
    if geometry.bounds[2] - geometry.bounds[0] > 180:
        raise ValueError("Este conector no admite polígonos que crucen el antimeridiano")
    if geometry.bounds[1] < -86 or geometry.bounds[3] > 86:
        raise ValueError("El polígono está fuera del rango del CRS de área equivalente")
    return geometry


def _bounding_box(geometry: AnalysisGeometry) -> BBox:
    west, south, east, north = geometry.bounds
    padding = GRID_RESOLUTION_DEGREES
    return BBox(
        max(-180.0, west - padding),
        max(-90.0, south - padding),
        min(180.0, east + padding),
        min(90.0, north + padding),
    )


def _parse_time_coordinate(time_values: np.ndarray | list[object]) -> list[date]:
    parsed: list[date] = []
    for t in time_values:
        if hasattr(t, "year") and hasattr(t, "month"):
            parsed.append(date(int(t.year), int(t.month), 1))
        else:
            ts = pd.Timestamp(t)
            parsed.append(date(int(ts.year), int(ts.month), 1))
    return parsed


def _aggregate_dataset(
    dataset: xr.Dataset,
    geometry: AnalysisGeometry,
    expected_months: tuple[date, ...],
) -> tuple[str, tuple[MonthlyPrecipitation, ...]]:
    var_name = None
    for candidate in (PRECIPITATION_VARIABLE, HARMONY_VARIABLE, "precipitationCal"):
        if candidate in dataset:
            var_name = candidate
            break
    if not var_name:
        raise DataIntegrityError(
            f"El NetCDF no contiene la variable esperada ({PRECIPITATION_VARIABLE!r} o {HARMONY_VARIABLE!r}). "
            f"Variables presentes: {list(dataset.data_vars)}"
        )

    lat_name = _find_coordinate(dataset, ("lat", "latitude"))
    lon_name = _find_coordinate(dataset, ("lon", "longitude"))
    time_name = _find_coordinate(dataset, ("time",))
    precipitation = dataset[var_name]
    lat_dimension = dataset[lat_name].dims
    lon_dimension = dataset[lon_name].dims
    time_dimension = dataset[time_name].dims
    if any(len(dims) != 1 for dims in (lat_dimension, lon_dimension, time_dimension)):
        raise DataIntegrityError("El NetCDF debe tener coordenadas 1D de tiempo, latitud y longitud")

    lat_dim, lon_dim, time_dim = lat_dimension[0], lon_dimension[0], time_dimension[0]
    if set(precipitation.dims) != {lat_dim, lon_dim, time_dim}:
        raise DataIntegrityError("La variable precipitation tiene dimensiones inesperadas")

    source_units = str(precipitation.attrs.get("units", "")).strip()
    if not source_units:
        raise DataIntegrityError("La variable precipitation no declara unidades")

    latitudes = np.asarray(dataset[lat_name].values, dtype=float)
    longitudes = np.asarray(dataset[lon_name].values, dtype=float)
    _validate_grid_axis(latitudes, "latitud")
    _validate_grid_axis(longitudes, "longitud")
    weights, region_area = _area_weights(geometry, latitudes, longitudes)
    values = np.asarray(
        precipitation.transpose(time_dim, lat_dim, lon_dim).values,
        dtype=float,
    )
    raw_times = dataset[time_name].values
    parsed_months = _parse_time_coordinate(raw_times)
    if values.shape[0] != len(parsed_months):
        raise DataIntegrityError("El tamaño del eje temporal no coincide con sus fechas")

    by_month: dict[date, np.ndarray] = {}
    for month, monthly_grid in zip(parsed_months, values, strict=True):
        if month in by_month:
            raise DataIntegrityError(f"El NetCDF repite el mes {month:%Y-%m}")
        by_month[month] = monthly_grid

    expected = set(expected_months)
    unexpected = sorted(by_month.keys() - expected)
    if unexpected:
        unexpected_months = ", ".join(month.strftime("%Y-%m") for month in unexpected)
        raise DataIntegrityError(f"Harmony devolvió meses fuera del rango: {unexpected_months}")

    missing = sorted(expected - by_month.keys())
    if missing:
        missing_months = ", ".join(month.strftime("%Y-%m") for month in missing)
        raise DataUnavailableError(f"Harmony no devolvió datos para: {missing_months}")

    monthly_values: list[MonthlyPrecipitation] = []
    for month in expected_months:
        grid = by_month[month]
        valid = np.isfinite(grid) & (weights > 0)
        valid_area = float(weights[valid].sum())
        if valid_area == 0:
            raise DataUnavailableError(
                f"No hay celdas válidas dentro del polígono para {month:%Y-%m}"
            )
        coverage = valid_area / region_area
        if coverage > 1.001:
            raise DataIntegrityError(
                f"La cobertura calculada excede el área del polígono para {month:%Y-%m}"
            )
        weighted_rate_or_depth = float(np.average(grid[valid], weights=weights[valid]))
        monthly_values.append(
            MonthlyPrecipitation(
                month=month,
                value=weighted_rate_or_depth,
                coverage_fraction=min(coverage, 1.0),
            )
        )

    return source_units, tuple(monthly_values)


def _find_coordinate(dataset: xr.Dataset, names: tuple[str, ...]) -> str:
    for name in names:
        if name in dataset.coords:
            return name
    raise DataIntegrityError(
        f"El NetCDF no contiene una coordenada reconocida: {', '.join(names)}"
    )


def _validate_grid_axis(coordinates: np.ndarray, name: str) -> None:
    if coordinates.ndim != 1 or coordinates.size == 0:
        raise DataIntegrityError(f"La coordenada de {name} está vacía o no es 1D")
    if not np.isfinite(coordinates).all():
        raise DataIntegrityError(f"La coordenada de {name} contiene valores no finitos")
    if coordinates.size > 1:
        differences = np.abs(np.diff(coordinates))
        if not np.allclose(
            differences,
            GRID_RESOLUTION_DEGREES,
            rtol=0,
            atol=1e-4,
        ):
            raise DataIntegrityError(
                f"La cuadrícula de {name} no conserva la resolución nativa de "
                f"{GRID_RESOLUTION_DEGREES} grados"
            )


def _area_weights(
    geometry: AnalysisGeometry,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> tuple[np.ndarray, float]:
    transformer = Transformer.from_crs("EPSG:4326", EQUAL_AREA_CRS, always_xy=True)
    projected_region = transform_geometry(
        geometry,
        transformer.transform,
        interleaved=False,
    )
    region_area = float(projected_region.area)
    if region_area <= 0:
        raise ValueError("El polígono debe cubrir un área mayor que cero")

    weights = np.zeros((len(latitudes), len(longitudes)), dtype=float)
    prepared = prep(projected_region)
    west, south, east, north = geometry.bounds
    half_cell = GRID_RESOLUTION_DEGREES / 2
    for row, latitude in enumerate(latitudes):
        cell_south, cell_north = latitude - half_cell, latitude + half_cell
        if cell_north <= south or cell_south >= north:
            continue
        for column, longitude in enumerate(longitudes):
            cell_west, cell_east = longitude - half_cell, longitude + half_cell
            if cell_east <= west or cell_west >= east:
                continue
            cell = Polygon(
                [
                    (cell_west, cell_south),
                    (cell_east, cell_south),
                    (cell_east, cell_north),
                    (cell_west, cell_north),
                ]
            )
            projected_cell = transform_geometry(
                cell,
                transformer.transform,
                interleaved=False,
            )
            if prepared.covers(projected_cell):
                weights[row, column] = projected_cell.area
            elif prepared.intersects(projected_cell):
                weights[row, column] = projected_region.intersection(projected_cell).area

    covered_area = float(weights.sum())
    if covered_area == 0:
        raise DataUnavailableError("La cuadrícula descargada no intersecta el polígono")
    return weights, region_area
