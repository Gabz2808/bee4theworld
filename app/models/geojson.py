from typing import Annotated, Literal

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
