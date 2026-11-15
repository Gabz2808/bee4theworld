from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

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


def are_geometries_equal(
    geom1: GeoJSONPolygon | dict[str, Any] | None,
    geom2: GeoJSONPolygon | dict[str, Any] | None,
    tolerance: float = 1e-5,
) -> bool:
    """Compara si dos geometrías poligonales GeoJSON son espacialmente equivalentes

    dentro de una tolerancia decimal especificada.
    """
    if geom1 is None or geom2 is None:
        return False
    coords1 = (
        geom1.coordinates
        if isinstance(geom1, GeoJSONPolygon)
        else (geom1.get("coordinates") if isinstance(geom1, dict) else None)
    )
    coords2 = (
        geom2.coordinates
        if isinstance(geom2, GeoJSONPolygon)
        else (geom2.get("coordinates") if isinstance(geom2, dict) else None)
    )
    if coords1 is None or coords2 is None:
        return False
    if len(coords1) != len(coords2):
        return False
    for ring1, ring2 in zip(coords1, coords2):
        if len(ring1) != len(ring2):
            return False
        for pt1, pt2 in zip(ring1, ring2):
            if abs(pt1[0] - pt2[0]) > tolerance or abs(pt1[1] - pt2[1]) > tolerance:
                return False
    return True

