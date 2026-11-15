from typing import Any, Literal

from pydantic import Field

from app.models.base import APIModel
from app.models.geojson import GeoJSONPolygon
from app.models.variables import AvailableInterval


class CatalogRegion(APIModel):
    id: str
    name: str
    description: str | None = None
    boundary_source: str
    boundary_version: str
    geom: GeoJSONPolygon


class CatalogVariable(APIModel):
    id: str
    name: str
    source: str
    dataset: str
    unit: str
    spatial_resolution: str
    temporal_resolution: Literal["monthly"]
    available_interval: AvailableInterval
    restrictions: list[str] = Field(default_factory=list)


class CatalogCombination(APIModel):
    region_id: str
    variable_id: str
    available_interval: AvailableInterval
    temporal_resolution: Literal["monthly"]
    is_ready_for_exploration: bool = True
    notes: str | None = None


class CatalogResponse(APIModel):
    status: Literal["success"] = "success"
    regions: list[CatalogRegion] = Field(min_length=1)
    variables: list[CatalogVariable] = Field(min_length=1)
    combinations: list[CatalogCombination] = Field(min_length=1)
