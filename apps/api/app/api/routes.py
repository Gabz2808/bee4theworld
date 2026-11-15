import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.supabase_client import get_supabase_client
from app.models.catalog import CatalogResponse
from app.models.errors import ErrorResponse
from app.models.exploration import ExplorationRequest, ExplorationResponse
from app.models.jobs import JobResponse
from app.services.exploration_service import get_catalog, run_exploration, validate_exploration_request
from app.services.gpm_imerg import GPMIMERGConnector
from app.services.job_manager import JobManager, make_job_fingerprint

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
    except Exception:  # noqa: BLE001 - boundary fallback
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
    supabase: Annotated[Any | None, Depends(get_optional_supabase)],
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
    connector: Annotated[GPMIMERGConnector, Depends(get_connector)],
    supabase: Annotated[Any | None, Depends(get_optional_supabase)],
) -> Any:
    # Deduplicación en vuelo: ante reintentos por timeout del proxy (90s) o peticiones simultáneas,
    # se reutiliza la misma tarea en ejecución en lugar de duplicar descargas remotas a NASA.
    fingerprint = make_job_fingerprint(request)
    job_mgr = JobManager.get_instance()

    return job_mgr.deduplicate_in_flight(
        fingerprint,
        lambda: run_exploration(
            request,
            connector=connector,
            supabase_client=supabase,
            request_headers=dict(request_http.headers),
        ),
    )


@router.post(
    "/api/v1/jobs/explorations",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Jobs"],
    summary="Inicia o deduplica un trabajo de exploración asíncrono para series largas",
    description=(
        "Permite al cliente iniciar extracciones multianuales que superan el límite del proxy (90s). "
        "Devuelve un job_id inmediatamente con estado 'running' y progreso por bloques, permitiendo "
        "polling desacoplado, deduplicación y cancelación segura."
    ),
    responses={
        202: {"description": "Trabajo aceptado o enlazado a ejecución activa."},
        400: {"model": ErrorResponse, "description": "Parámetros inválidos o fuera de cobertura."},
        422: {"model": ErrorResponse, "description": "Error de validación en la solicitud."},
    },
)
def post_v1_jobs_explorations(
    request: ExplorationRequest,
    request_http: Request,
    connector: Annotated[GPMIMERGConnector, Depends(get_connector)],
    supabase: Annotated[Any | None, Depends(get_optional_supabase)],
) -> JobResponse:
    validate_exploration_request(request)
    headers = dict(request_http.headers)
    job_mgr = JobManager.get_instance()

    def _execute(progress_cb: Any, cancel_event: Any) -> ExplorationResponse:
        return run_exploration(
            request,
            connector=connector,
            supabase_client=supabase,
            request_headers=headers,
            progress_callback=progress_cb,
            cancel_check=cancel_event.is_set,
        )

    return job_mgr.submit_exploration_job(request, _execute)


@router.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobResponse,
    tags=["Jobs"],
    summary="Consulta estado, avance y resultado de un trabajo de exploración",
    responses={
        200: {"description": "Estado y progreso del trabajo."},
        404: {"model": ErrorResponse, "description": "Trabajo no encontrado."},
    },
)
def get_v1_job_status(job_id: str) -> JobResponse:
    job = JobManager.get_instance().get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo con identificador '{job_id}' no encontrado o ha expirado.",
        )
    return job


@router.delete(
    "/api/v1/jobs/{job_id}",
    response_model=JobResponse,
    tags=["Jobs"],
    summary="Cancela un trabajo de exploración en ejecución",
    responses={
        200: {"description": "Trabajo cancelado."},
        404: {"model": ErrorResponse, "description": "Trabajo no encontrado."},
    },
)
def delete_v1_job(job_id: str) -> JobResponse:
    job = JobManager.get_instance().cancel_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Trabajo con identificador '{job_id}' no encontrado o ha expirado.",
        )
    return job
