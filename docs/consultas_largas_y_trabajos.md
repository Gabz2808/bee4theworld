# Consultas Históricas desde 1998 y Manejo de Trabajos Largos (Issue #20)

**Fecha:** 15 de noviembre de 2026  
**Módulo:** `apps/api` (FastAPI / GPM IMERG / NASA Harmony)  
**Issues relacionados:** #20 (Backend 6/7), #3, #10, #19  

---

## 1. Contexto y Problema

1. **Restricción de fechas arbitraria:** El backend limitaba las exploraciones al período `2001-01-01` a `2024-12-31`. Sin embargo, la colección `GPM_3IMERGM` V07 contiene datos desde enero de 1998.
2. **Límite de espera (Timeout) del proxy frontend (90 segundos):** El proxy de Next.js (`apps/web/src/app/api/backend/[endpoint]/route.ts`) tiene un `AbortSignal.timeout(90000)`. Una petición multianual en vivo a NASA Harmony (por ejemplo, 5 a 27 años) puede requerir varios minutos para consultar CMR, generar el trabajo de subsetting espacial en Harmony y descargar decenas o cientos de archivos NetCDF.
3. **Riesgo de solicitudes duplicadas:** Al vencer el timeout de 90 segundos, el frontend devuelve `504 BACKEND_TIMEOUT`. Si el usuario reintenta inmediatamente, sin deduplicación el servidor lanzaría un segundo trabajo remoto idéntico a NASA, duplicando consumo de ancho de banda y arriesgando bloqueos por saturación o rate-limiting.

---

## 2. Comprobación y Verificación de la Colección 1998–2000

Antes de habilitar 1998 en el catálogo, se ejecutó una auditoría exhaustiva en NASA CMR y una extracción en vivo en NASA Harmony:

1. **Catálogo NASA CMR:**
   - Consulta a `https://cmr.earthdata.nasa.gov/search/granules.json` con `short_name=GPM_3IMERGM`, `version=07` y rango temporal `1998-01-01T00:00:00Z` a `2000-12-31T23:59:59Z`.
   - **Resultado:** 36 gránulos correspondientes a los 36 meses únicos consecutivos (enero 1998 a diciembre 2000).
   - **Meses faltantes:** 0.
   - **Meses duplicados:** 0.
   - **Colección:** `C2723754851-GES_DISC` (idéntica a la colección 2001–2024).

2. **Extracción satelital real con NASA Harmony:**
   - Se ejecutó una extracción real para enero de 1998 (`1998-01-01` a `1998-01-31`) sobre una geometría de control.
   - **Archivo NetCDF generado y descargado:** `..._GPM_3IMERGM.07_3B-MO.MS.MRG.3IMERG.19980101-S000000-E235959.01.V07B_subsetted.nc4`.
   - **Tasa de precipitación:** `0.0282 mm/hr`.
   - **Cobertura espacial territorial:** `100.0%`.
   - **Identificador de gránulo:** `G3281475020-GES_DISC`.

---

## 3. Arquitectura de Solución Implementada

### 3.1 Extensión del Catálogo (`MIN_SUPPORTED_DATE = 1998-01-01`)
- En `apps/api/app/services/exploration_service.py`, `MIN_SUPPORTED_DATE` se actualizó a `date(1998, 1, 1)`.
- El endpoint `GET /api/v1/catalog` anuncia `available_interval`, `declared_interval` y `verified_interval` comenzando en `1998-01-01`.
- Para `costa-rica-continental`, la nota indica que el período `2001-2024` está disponible de inmediato en archivo preprocesado (demo offline) y el período `1998-2000` se resuelve bajo demanda.

### 3.2 División por Bloques (Chunking) y Reintentos en Conector IMERG
- En `apps/api/app/services/gpm_imerg.py`, consultas mayores a 12 meses se particionan automáticamente en bloques anuales (`CHUNK_MAX_MONTHS = 12`).
- Cada bloque se procesa con hasta 2 intentos ante fallos transitorios de red.
- Si un bloque experimenta un fallo persistente, se lanza `DataUnavailableError` indicando con precisión el año del bloque afectado.
- Se soporta un callback de progreso (`progress_callback`) y comprobación de cancelación (`cancel_check`).

### 3.3 Deduplicación en Vuelo (Single-Flight Pattern)
- En `apps/api/app/services/job_manager.py`:
  - `deduplicate_in_flight(fingerprint, execute_fn)`: Si dos clientes solicitan la misma exploración, o si un cliente reintenta tras un timeout de proxy de 90s, el segundo llamado se suscribe a la tarea que ya está en ejecución en lugar de iniciar una segunda consulta a NASA.
  - Si el proxy se desconecta, la tarea en segundo plano no se aborta si está activa; finaliza su procesamiento y persiste el resultado en la caché.
  - Al reintentar el cliente, la consulta responde inmediatamente como `hit` de caché.

### 3.4 API de Trabajos Asíncronos (`/api/v1/jobs`)
Para soportar flujos largos desacoplados del frontend:
- **`POST /api/v1/jobs/explorations`** (HTTP 202 Accepted): Inicia o deduplica un trabajo asíncrono y devuelve `job_id`, `status` y `progress`.
- **`GET /api/v1/jobs/{job_id}`** (HTTP 200 / 404): Devuelve el estado actual (`pending`, `running`, `completed`, `failed`, `cancelled`), porcentaje de avance y resultado completo `result` si ya terminó.
- **`DELETE /api/v1/jobs/{job_id}`** (HTTP 200 / 404): Permite cancelar un trabajo en ejecución, interrumpiendo descargas de bloques pendientes.

---

## 4. Matriz de Estados de Trabajos

| Estado | Significado | Comportamiento del Cliente |
| --- | --- | --- |
| `pending` | Trabajo encolado esperando hilo disponible | Esperar y reintentar polling (ej. cada 2-3 s) |
| `running` | Extrayendo gránulos por bloques desde Harmony | Mostrar barra de progreso con porcentaje y mensaje |
| `completed` | Extracción y análisis completados con éxito | Consumir el campo `result` (`ExplorationResponse`) |
| `failed` | Error de red o en datos satelitales | Mostrar mensaje de error seguro de `error` |
| `cancelled` | Cancelado por el usuario vía `DELETE` | Actualizar UI a estado inactivo |
