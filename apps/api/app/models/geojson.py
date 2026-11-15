from typing import Annotated, Any, Literal

from pydantic import Field, model_validator
from shapely.geometry import shape

from app.models.base import APIModel

Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Position = tuple[Longitude, Latitude]
LinearRing = Annotated[list[Position], Field(min_length=4)]


class GeoJSONPolygon(APIModel):
    type: Literal["Polygon"]
    coordinates: Annotated[list[LinearRing], Field(min_length=1)]

    @model_validator(mode="after")
    def rings_must_be_closed(self) -> "GeoJSONPolygon":
        for ring in self.coordinates:
            if ring[0] != ring[-1]:
                raise ValueError("Cada anillo del polígono debe estar cerrado")
        return self


class GeoJSONMultiPolygon(APIModel):
    type: Literal["MultiPolygon"]
    coordinates: Annotated[list[Annotated[list[LinearRing], Field(min_length=1)]], Field(min_length=1)]

    @model_validator(mode="after")
    def rings_must_be_closed(self) -> "GeoJSONMultiPolygon":
        for polygon in self.coordinates:
            for ring in polygon:
                if ring[0] != ring[-1]:
                    raise ValueError("Cada anillo del multipolígono debe estar cerrado")
        return self


def are_geometries_equal(
    geom1: GeoJSONPolygon | GeoJSONMultiPolygon | dict[str, Any] | None,
    geom2: GeoJSONPolygon | GeoJSONMultiPolygon | dict[str, Any] | None,
    tolerance: float = 1e-5,
) -> bool:
    """Compara si dos geometrías poligonales GeoJSON son espacialmente equivalentes

    dentro de una tolerancia decimal especificada.
    """
    if geom1 is None or geom2 is None:
        return False
    obj1 = geom1.model_dump(mode="json") if isinstance(geom1, (GeoJSONPolygon, GeoJSONMultiPolygon)) else geom1
    obj2 = geom2.model_dump(mode="json") if isinstance(geom2, (GeoJSONPolygon, GeoJSONMultiPolygon)) else geom2
    if obj1.get("type") != obj2.get("type"):
        return False
    try:
        return shape(obj1).equals_exact(shape(obj2), tolerance)
    except (TypeError, ValueError, KeyError):
        return False

