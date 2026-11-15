from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Cargar automáticamente variables de entorno desde apps/api/.env o .env raíz
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

from app.api.routes import router
from app.core.security import SecurityLimitsMiddleware, get_cors_origins

app = FastAPI(
    title="Iyök API",
    description="API de inteligencia y detección de tendencias del sistema terrestre para Iyök (NASA Space Apps Challenge).",
    version="1.0.0",
)

# 1. Middleware de límites de seguridad (tamaño de cuerpo y rate limiting)
app.add_middleware(SecurityLimitsMiddleware)

# 2. Middleware de CORS con orígenes acordados (nunca wildcard con credenciales)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Iyok-Write-Key"],
)


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        400: "INVALID_REQUEST",
        404: "NOT_FOUND",
        413: "PAYLOAD_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMIT_EXCEEDED",
        502: "UPSTREAM_SERVICE_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    code = (exc.headers or {}).get("X-Iyok-Error-Code", code_map.get(exc.status_code, "ERROR"))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
                "details": [],
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = []
    for error in exc.errors():
        locs = [str(x) for x in error.get("loc", []) if x not in ("body",)]
        field = ".".join(locs) if locs else None
        details.append({"field": field, "issue": error.get("msg", "Valor inválido")})

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "La solicitud contiene parámetros con formato inválido.",
                "details": details,
            }
        },
    )


app.include_router(router)
