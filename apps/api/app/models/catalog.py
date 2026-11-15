from typing import Literal

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
    declared_interval: AvailableInterval | None = None
    verified_interval: AvailableInterval | None = None
    known_gaps: list[AvailableInterval] = Field(default_factory=list)
    doi_or_link: str | None = "https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07"
    source_status: Literal["available", "verified", "on_demand", "unavailable", "source_unavailable"] = "available"
    restrictions: list[str] = Field(default_factory=list)


class CatalogCombination(APIModel):
    region_id: str
    variable_id: str
    available_interval: AvailableInterval
    declared_interval: AvailableInterval | None = None
    verified_interval: AvailableInterval | None = None
    known_gaps: list[AvailableInterval] = Field(default_factory=list)
    source_status: Literal["available", "verified", "on_demand", "unavailable", "source_unavailable"] = "available"
    temporal_resolution: Literal["monthly"]
    is_ready_for_exploration: bool = True
    notes: str | None = None


class CatalogResponse(APIModel):
    status: Literal["success"] = "success"
    regions: list[CatalogRegion] = Field(min_length=1)
    variables: list[CatalogVariable] = Field(min_length=1)
    combinations: list[CatalogCombination] = Field(min_length=1)
