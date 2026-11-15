from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.exploration import ExplorationRequest, ExplorationResponse


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percent: float = Field(default=0.0, ge=0.0, le=100.0, description="Porcentaje de avance estimado")
    completed_steps: int = Field(default=0, ge=0, description="Meses o bloques completados")
    total_steps: int = Field(default=0, ge=0, description="Meses o bloques totales")
    current_stage: str = Field(default="queued", description="Etapa actual del procesamiento")
    message: str = Field(default="", description="Mensaje explicativo del estado actual")


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: JobStatus
    progress: JobProgress
    created_at: datetime
    updated_at: datetime
    request: ExplorationRequest
    result: ExplorationResponse | None = None
    error: dict[str, Any] | None = None
    links: dict[str, str] = Field(default_factory=dict)
