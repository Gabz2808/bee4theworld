from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from app.models.base import APIModel


class AvailableInterval(APIModel):
    start: date
    end: date

    @model_validator(mode="after")
    def end_must_not_precede_start(self) -> "AvailableInterval":
        if self.end < self.start:
            raise ValueError("La fecha final debe ser igual o posterior a la inicial")
        return self


class Variable(APIModel):
    id: Literal["precipitation"]
    name: str
    source: str
    unit: str
    available_interval: AvailableInterval


class VariablesResponse(APIModel):
    status: Literal["success"]
    data: list[Variable] = Field(min_length=1)
