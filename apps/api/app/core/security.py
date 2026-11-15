"""Módulo de seguridad, límites y control de acceso para la API Iyök.

Implementa los requisitos de seguridad antes de exposición pública (Issue #16):
- Configuración segura de orígenes CORS.
- Límites de tamaño de solicitud (payload) para prevenir DoS.
- Límites de complejidad espacial (vértices y extensión de área) en polígonos.
- Limitador de frecuencia y concurrencia de solicitudes (Rate Limiter) en memoria.
- Modelo de autorización de escritura separado de lectura.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Límites de protección por defecto
DEFAULT_MAX_REQUEST_BODY_BYTES = 1 * 1024 * 1024  # 1 MB
MAX_POLYGON_VERTICES = 500
MAX_BBOX_DELTA_LON = 15.0  # Grados de longitud (~1,650 km en el ecuador)
MAX_BBOX_DELTA_LAT = 10.0  # Grados de latitud (~1,110 km)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


def get_cors_origins() -> list[str]:
    """Obtiene los orígenes permitidos para CORS desde variables de entorno o defaults seguros."""
    env_origins = os.environ.get("CORS_ORIGINS", "").strip()
    if not env_origins:
        return list(DEFAULT_CORS_ORIGINS)

    origins = [orig.strip() for orig in env_origins.split(",") if orig.strip()]
    return origins if origins else list(DEFAULT_CORS_ORIGINS)


def is_write_authorized(headers: dict[str, str] | None = None) -> bool:
    """Verifica si la operación de escritura/persistencia está autorizada.

    Separa lectura de escritura:
    - Si IYOK_ALLOW_WRITE es 'false', se deshabilita la escritura en Supabase.
    - Si IYOK_WRITE_KEY está definida en el entorno, exige que el header 'X-Iyok-Write-Key' coincida.
    - Por defecto en entorno local (sin IYOK_WRITE_KEY definida), permite la persistencia.
    """
    allow_write = os.environ.get("IYOK_ALLOW_WRITE", "true").strip().lower() != "false"
    if not allow_write:
        return False

    required_key = os.environ.get("IYOK_WRITE_KEY", "").strip()
    if not required_key:
        return True

    if not headers:
        return False

    client_key = headers.get("x-iyok-write-key") or headers.get("X-Iyok-Write-Key") or ""
    return client_key == required_key


def validate_polygon_complexity_and_area(coordinates: list[list[list[float]]]) -> None:
    """Valida que el polígono no supere los límites de vértices ni la extensión máxima de área.

    Previene ataques de agotamiento computacional o solicitudes planetarias desmedidas.
    """
    if not coordinates or not coordinates[0]:
        return

    # Codex (Manuel): contar también los anillos interiores para limitar el trabajo total.
    ring = coordinates[0]
    num_vertices = sum(len(part) for part in coordinates)

    if num_vertices > MAX_POLYGON_VERTICES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"El polígono supera la complejidad máxima permitida de {MAX_POLYGON_VERTICES} vértices "
                f"(enviados: {num_vertices}). Simplifique la geometría para evitar sobrecarga computacional."
            ),
        )

    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]

    delta_lon = max(lons) - min(lons)
    delta_lat = max(lats) - min(lats)

    if delta_lon > MAX_BBOX_DELTA_LON or delta_lat > MAX_BBOX_DELTA_LAT:
        raise HTTPException(
            status_code=422,
            detail=(
                f"El área del polígono supera la extensión espacial máxima permitida "
                f"(máximo {MAX_BBOX_DELTA_LON}° de longitud y {MAX_BBOX_DELTA_LAT}° de latitud; "
                f"enviado: {delta_lon:.2f}° lon × {delta_lat:.2f}° lat). "
                "Defina un ámbito espacial regional o nacional representativo."
            ),
        )


class InMemoryRateLimiter:
    """Limitador de frecuencia en memoria basado en ventana deslizante por IP cliente."""

    def __init__(self, requests_per_minute: int = 60, exploration_limit_per_minute: int = 15) -> None:
        self.requests_per_minute = requests_per_minute
        self.exploration_limit_per_minute = exploration_limit_per_minute
        self._general_hits: dict[str, list[float]] = defaultdict(list)
        self._exploration_hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str, is_exploration: bool = False) -> tuple[bool, int]:
        now = time.time()
        window_start = now - 60.0

        hits_dict = self._exploration_hits if is_exploration else self._general_hits
        limit = self.exploration_limit_per_minute if is_exploration else self.requests_per_minute

        # Filtrar hits fuera de la ventana de 60 segundos
        hits = [t for t in hits_dict[client_ip] if t > window_start]
        hits_dict[client_ip] = hits

        if len(hits) >= limit:
            retry_after = int(60.0 - (now - hits[0])) if hits else 60
            return False, max(1, retry_after)

        hits.append(now)
        return True, 0

    def reset(self) -> None:
        """Reinicia el estado del limitador (útil para pruebas)."""
        self._general_hits.clear()
        self._exploration_hits.clear()


# Instancia singleton del limitador de frecuencia
rate_limiter = InMemoryRateLimiter()


class SecurityLimitsMiddleware(BaseHTTPMiddleware):
    """Middleware HTTP para validar tamaño máximo de payload y tasa de solicitudes."""

    def __init__(
        self,
        app,
        max_body_bytes: int = DEFAULT_MAX_REQUEST_BODY_BYTES,
        limiter: InMemoryRateLimiter | None = None,
    ) -> None:
        super().__init__(app)
        self.max_body_bytes = max_body_bytes
        self.limiter = limiter or rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Comprobación de tamaño máximo de cuerpo (Content-Length)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length_int = int(content_length)
                if length_int > self.max_body_bytes:
                    return Response(
                        status_code=413,
                        content=(
                            b'{"error":{"code":"PAYLOAD_TOO_LARGE",'
                            b'"message":"El tamano del cuerpo de la solicitud supera el limite permitido de 1 MB.",'
                            b'"details":[]}}'
                        ),
                        media_type="application/json",
                    )
            except ValueError:
                pass

        # Codex (Manuel): limitar los bytes recibidos incluso sin Content-Length fiable.
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > self.max_body_bytes:
                return Response(
                    status_code=413,
                    content=b'{"error":{"code":"PAYLOAD_TOO_LARGE","message":"El tamano del cuerpo de la solicitud supera el limite permitido de 1 MB.","details":[]}}',
                    media_type="application/json",
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)

        # 2. Control de frecuencia (Rate Limiting)
        # Omitir OPTIONS (preflight CORS) y ping
        if request.method != "OPTIONS" and request.url.path != "/ping":
            client_ip = request.client.host if request.client else "unknown"
            is_exploration = "/api/v1/explorations" in request.url.path

            allowed, retry_after = self.limiter.is_allowed(client_ip, is_exploration=is_exploration)
            if not allowed:
                return Response(
                    status_code=429,
                    content=(
                        b'{"error":{"code":"RATE_LIMIT_EXCEEDED",'
                        b'"message":"Limite de frecuencia de solicitudes excedido. Intente nuevamente en unos instantes.",'
                        b'"details":[]}}'
                    ),
                    media_type="application/json",
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
