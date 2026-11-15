from typing import Any

from pydantic import Field

from app.models.base import APIModel


class ErrorDetail(APIModel):
    field: str | None = None
    issue: str


class ErrorBody(APIModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(APIModel):
    error: ErrorBody
