from typing import Literal

from pydantic import Field

from app.models.base import APIModel
from app.models.geojson import GeoJSONPolygon


class Region(APIModel):
    id: str
    name: str
    description: str | None = None
    boundary_source: str
    boundary_version: str
    geom: GeoJSONPolygon


class RegionsResponse(APIModel):
    status: Literal["success"]
    data: list[Region] = Field(min_length=1)
