from __future__ import annotations

import hashlib
import json
import logging
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Callable

from app.models.exploration import ExplorationRequest, ExplorationResponse
from app.models.jobs import JobProgress, JobResponse, JobStatus

logger = logging.getLogger(__name__)


def make_job_fingerprint(request: ExplorationRequest) -> str:
    payload = {
        "variable_id": request.variable_id,
        "region_id": request.region_id,
        "region": request.region.model_dump() if request.region else None,
        "start_date": request.start_date.isoformat() if request.start_date else None,
        "end_date": request.end_date.isoformat() if request.end_date else None,
        "temporal_resolution": request.temporal_resolution,
    }
    raw = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class JobManager:
    _instance: JobManager | None = None
    _lock = threading.Lock()

    def __init__(self, max_workers: int = 4) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._fingerprint_to_job: dict[str, str] = {}
        self._in_flight_futures: dict[str, Future[Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="iyok-worker")
        self._state_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> JobManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def submit_exploration_job(
        self,
        request: ExplorationRequest,
        run_fn: Callable[[Callable[[int, int, str], None], threading.Event], ExplorationResponse],
    ) -> JobResponse:
        fingerprint = make_job_fingerprint(request)
        now = datetime.now(UTC)

        with self._state_lock:
            # 1. Deduplicación: Si ya hay un trabajo pendiente o en ejecución para esta consulta
            existing_job_id = self._fingerprint_to_job.get(fingerprint)
            if existing_job_id and existing_job_id in self._jobs:
                existing = self._jobs[existing_job_id]
                if existing["status"] in (JobStatus.PENDING, JobStatus.RUNNING):
                    logger.info("Deduplicación de trabajo activa para %s (job_id: %s)", fingerprint, existing_job_id)
                    return self._build_response(existing_job_id)
                if existing["status"] == JobStatus.COMPLETED and existing.get("result"):
                    return self._build_response(existing_job_id)

            job_id = f"job-{uuid.uuid4().hex[:12]}"
            cancel_event = threading.Event()
            job_data: dict[str, Any] = {
                "job_id": job_id,
                "fingerprint": fingerprint,
                "request": request,
                "status": JobStatus.PENDING,
                "progress": JobProgress(
                    percent=0.0,
                    completed_steps=0,
                    total_steps=0,
                    current_stage="queued",
                    message="Trabajo en cola de procesamiento",
                ),
                "created_at": now,
                "updated_at": now,
                "result": None,
                "error": None,
                "cancel_event": cancel_event,
            }
            self._jobs[job_id] = job_data
            self._fingerprint_to_job[fingerprint] = job_id

        # Iniciar ejecución en hilo desacoplado
        def _worker() -> None:
            with self._state_lock:
                job_data["status"] = JobStatus.RUNNING
                job_data["updated_at"] = datetime.now(UTC)
                job_data["progress"].current_stage = "running"
                job_data["progress"].message = "Extrayendo y procesando datos..."

            def _progress_cb(completed: int, total: int, msg: str) -> None:
                with self._state_lock:
                    job_data["updated_at"] = datetime.now(UTC)
                    job_data["progress"].completed_steps = completed
                    job_data["progress"].total_steps = total
                    job_data["progress"].message = msg
                    if total > 0:
                        job_data["progress"].percent = round((completed / total) * 100.0, 1)

            try:
                res = run_fn(_progress_cb, cancel_event)
                with self._state_lock:
                    if cancel_event.is_set():
                        job_data["status"] = JobStatus.CANCELLED
                        job_data["progress"].current_stage = "cancelled"
                        job_data["progress"].message = "Trabajo cancelado por el usuario"
                    else:
                        job_data["status"] = JobStatus.COMPLETED
                        job_data["progress"].percent = 100.0
                        job_data["progress"].current_stage = "completed"
                        job_data["progress"].message = "Procesamiento completado con éxito"
                        job_data["result"] = res
                    job_data["updated_at"] = datetime.now(UTC)
            except Exception as e:
                with self._state_lock:
                    if cancel_event.is_set():
                        job_data["status"] = JobStatus.CANCELLED
                        job_data["progress"].current_stage = "cancelled"
                        job_data["progress"].message = "Trabajo cancelado por el usuario"
                    else:
                        logger.exception("Error ejecutando trabajo %s: %s", job_id, e)
                        job_data["status"] = JobStatus.FAILED
                        job_data["progress"].current_stage = "failed"
                        job_data["progress"].message = f"Error durante la extracción: {e}"
                        job_data["error"] = {
                            "code": type(e).__name__,
                            "message": str(e),
                        }
                    job_data["updated_at"] = datetime.now(UTC)

        self._executor.submit(_worker)
        return self._build_response(job_id)

    def get_job(self, job_id: str) -> JobResponse | None:
        with self._state_lock:
            if job_id not in self._jobs:
                return None
            return self._build_response(job_id)

    def cancel_job(self, job_id: str) -> JobResponse | None:
        with self._state_lock:
            if job_id not in self._jobs:
                return None
            job_data = self._jobs[job_id]
            if job_data["status"] in (JobStatus.PENDING, JobStatus.RUNNING):
                job_data["cancel_event"].set()
                job_data["status"] = JobStatus.CANCELLED
                job_data["updated_at"] = datetime.now(UTC)
                job_data["progress"].current_stage = "cancelled"
                job_data["progress"].message = "Cancelación solicitada por el usuario"
            return self._build_response(job_id)

    def deduplicate_in_flight(
        self,
        fingerprint: str,
        execute_fn: Callable[[], ExplorationResponse],
    ) -> ExplorationResponse:
        """Deduplica llamadas sincrónicas concurrentes hacia una misma consulta.

        Si otra petición ya está ejecutando la misma extracción (por ejemplo,
        un reintento del cliente tras timeout de proxy de 90s), espera y reutiliza
        el mismo resultado en lugar de duplicar la descarga remota.
        """
        with self._state_lock:
            future = self._in_flight_futures.get(fingerprint)
            if future is None or future.done():
                future = self._executor.submit(execute_fn)
                self._in_flight_futures[fingerprint] = future

        try:
            return future.result()
        finally:
            with self._state_lock:
                if self._in_flight_futures.get(fingerprint) is future and future.done():
                    self._in_flight_futures.pop(fingerprint, None)

    def _build_response(self, job_id: str) -> JobResponse:
        job = self._jobs[job_id]
        return JobResponse(
            job_id=job["job_id"],
            status=job["status"],
            progress=job["progress"],
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            request=job["request"],
            result=job["result"],
            error=job["error"],
            links={
                "status": f"/api/v1/jobs/{job_id}",
                "cancel": f"/api/v1/jobs/{job_id}",
            },
        )

    def clear(self) -> None:
        """Limpia el registro de trabajos (para uso en tests)."""
        with self._state_lock:
            self._jobs.clear()
            self._fingerprint_to_job.clear()
            self._in_flight_futures.clear()
