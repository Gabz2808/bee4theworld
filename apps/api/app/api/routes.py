import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.supabase_client import SupabaseConfigurationError, get_supabase_client
from app.models.catalog import CatalogResponse
from app.models.errors import ErrorResponse
from app.models.exploration import ExplorationRequest, ExplorationResponse
from app.services.exploration_service import get_catalog, run_exploration
from app.services.gpm_imerg import GPMIMERGConnector

router = APIRouter()


def get_connector() -> GPMIMERGConnector:
    return GPMIMERGConnector()


def get_optional_supabase() -> Any | None:
    source = os.environ.get("IYOK_DATA_SOURCE", "auto").strip().lower()
    if source == "nasa":
        return None
    if source != "auto":
        raise HTTPException(status_code=503, detail="Configuración de fuente de datos no válida.")
    try:
        return get_supabase_client()
    except (SupabaseConfigurationError, Exception):
        return None


@router.get(
    "/ping",
    tags=["Health"],
    summary="Health check del servicio",
)
def ping() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/api/v1/catalog",
    response_model=CatalogResponse,
    tags=["Catalog"],
    summary="Catálogo unificado de opciones y cobertura disponible",
    description=(
        "Devuelve las regiones geográficas, variables de ciencias de la Tierra y sus "
        "combinaciones disponibles con intervalos de cobertura reales e indicaciones de restricciones."
    ),
    responses={
        200: {"description": "Catálogo completo disponible para exploración."},
    },
)
def get_v1_catalog(
    supabase: Any | None = Depends(get_optional_supabase),
) -> CatalogResponse:
    return get_catalog(supabase_client=supabase)


@router.post(
    "/api/v1/explorations",
    response_model=ExplorationResponse,
    status_code=status.HTTP_200_OK,
    tags=["Explorations"],
    summary="Consulta analítica y detección de tendencias terrestres",
    description=(
        "Recibe un identificador de región (ej. 'costa-rica-continental') o polígono, "
        "variable y fechas; orquesta la obtención satelital (Supabase/NASA), calcula "
        "la serie temporal mensual, línea base y anomalías en mm, acumulados anuales "
        "y evalúa la tendencia mediante estimador Theil-Sen y el test de Mann-Kendall."
    ),
    responses={
        200: {"description": "Serie y análisis correspondientes exactamente a la selección."},
        400: {"model": ErrorResponse, "description": "Parámetros inválidos o fuera de cobertura."},
        404: {"model": ErrorResponse, "description": "Identificador de región o variable no encontrado."},
        422: {"model": ErrorResponse, "description": "Error de validación de campos."},
        502: {"model": ErrorResponse, "description": "Fallo en servicio satelital externo."},
    },
)
def post_v1_explorations(
    request: ExplorationRequest,
    request_http: Request,
    connector: GPMIMERGConnector = Depends(get_connector),
    supabase: Any | None = Depends(get_optional_supabase),
) -> ExplorationResponse:
    return run_exploration(
        request,
        connector=connector,
        supabase_client=supabase,
        request_headers=dict(request_http.headers),
    )
