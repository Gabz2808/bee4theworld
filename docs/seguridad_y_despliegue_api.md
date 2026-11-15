# Seguridad, Límites y Condiciones de Despliegue de la API Iyök

*Actualizado: 14 de noviembre de 2026 — Resolución de Issue #16 (Backend 2/7)*

Este documento especifica los controles de acceso, límites de seguridad, configuración de CORS y directrices de despliegue antes de exponer la API a entornos compartidos o públicos.

---

## 1. Modelo de Acceso del MVP

| Nivel de Operación | Endpoints / Flujo | Modelo de Acceso | Mecanismo de Control |
| :--- | :--- | :--- | :--- |
| **Salud y Monitoreo** | `GET /ping` | Público | Sin autenticación; excluido de rate limit estricto. |
| **Lectura de Catálogo** | `GET /api/v1/catalog` | Público | Consulta de regiones, variables y combinaciones soportadas. |
| **Consulta y Análisis** | `POST /api/v1/explorations` | Abierto al cliente legítimo | Procesa exploraciones satelitales, tendencias y anomalías. Sujeto a límites de área, complejidad y frecuencia. |
| **Persistencia / Escritura** | `save_to_supabase` (escritura en Supabase) | **Controlado y separado de lectura** | Solo persiste si la escritura está habilitada (`IYOK_ALLOW_WRITE=true`) y, si se configura `IYOK_WRITE_KEY`, exige la cabecera `X-Iyok-Write-Key`. Las geometrías personalizadas no se escriben en Supabase (se aíslan en caché local). |

---

## 2. Límites de Protección contra Abuso y DoS

Para evitar sobrecargas computacionales, consumos desmedidos de ancho de banda o ataques de denegación de servicio (DoS) a la API y a los servicios upstream de NASA Earthdata:

1. **Tamaño máximo del cuerpo de solicitud (Payload Limit):**
   * Límite: **1 MB** (`1,048,576 bytes`).
   * Respuesta ante exceso: `HTTP 413 Payload Too Large` con código `"PAYLOAD_TOO_LARGE"`.
2. **Complejidad del polígono (Vertex Limit):**
   * Límite: Máximo **500 vértices** en el anillo exterior de la geometría.
   * Respuesta ante exceso: `HTTP 422 Unprocessable Entity` con código `"UNPROCESSABLE_ENTITY"`.
3. **Extensión espacial máxima (Bounding Box Limit):**
   * Límite: Máximo **15.0° de longitud** y **10.0° de latitud** ($\Delta\text{lon} \le 15.0^\circ, \Delta\text{lat} \le 10.0^\circ$).
   * Justificación: Permite cubrir cualquier ámbito de estudio local, provincial o nacional en Centro y Sudamérica (ej. Costa Rica $\sim 3.5^\circ \times 2.8^\circ$, Canal de Panamá $\sim 0.5^\circ \times 0.5^\circ$), previniendo consultas globales o continentales masivas.
   * Respuesta ante exceso: `HTTP 422 Unprocessable Entity`.
4. **Frecuencia y Concurrencia (Rate Limiting):**
   * Limitador en memoria por IP cliente:
     * General: 60 solicitudes por minuto.
     * Exploraciones satelitales analíticas (`POST /api/v1/explorations`): 15 solicitudes por minuto.
   * Respuesta ante exceso: `HTTP 429 Too Many Requests` con código `"RATE_LIMIT_EXCEEDED"` y cabecera `Retry-After: <segundos>`.

---

## 3. Configuración de CORS

* **CORS no es un mecanismo de control de acceso ni de autenticación:** Es una restricción del navegador para aislar contextos de origen.
* **Orígenes permitidos:**
  * Se configuran mediante la variable de entorno `CORS_ORIGINS` (separados por coma).
  * Orígenes por defecto para desarrollo:
    * `http://localhost:3000` (Next.js)
    * `http://127.0.0.1:3000`
    * `http://localhost:5173` (Vite / herramientas)
    * `http://127.0.0.1:5173`
  * En producción, definir explícitamente el dominio del frontend (ej. `https://iyok.earth,https://bee4theworld.vercel.app`).
* **Credenciales y métodos:**
  * `allow_credentials=True` se habilita únicamente sobre la lista explícita de orígenes de confianza.
  * Nunca se combina `allow_origins=["*"]` con `allow_credentials=True`.
  * Métodos autorizados: `GET`, `POST`, `OPTIONS`.
  * Cabeceras autorizadas: `Content-Type`, `Authorization`, `X-Iyok-Write-Key`.

---

## 4. Gestión de Secretos y Privilegios en Supabase

1. **Credenciales del Servidor (`service_role`):**
   * La clave privilegiada `SUPABASE_SECRET_KEY` pertenece **exclusivamente al backend** (`apps/api/.env`).
   * **Nunca exponerla en el navegador**, ni en `apps/web/.env`, ni en commits de Git.
2. **Políticas de Base de Datos (Row Level Security):**
   * Las tablas `public.variables`, `public.regions`, `public.ingestion_runs` y `public.processed_data` tienen RLS habilitado.
   * Los roles anónimos (`anon`) y autenticados del navegador no tienen permisos directos de inserción o eliminación; el backend actúa como guardián autorizador.

---

## 5. Variables de Entorno para Despliegue

| Variable | Tipo | Requerida | Propósito |
| :--- | :--- | :--- | :--- |
| `EARTHDATA_TOKEN` | String | Sí (en modo `nasa`/`auto`) | Token de autenticación de NASA Earthdata para ingesta satelital en vivo. |
| `SUPABASE_URL` | URL | Opcional (modo `auto`) | URL del proyecto Supabase. |
| `SUPABASE_SECRET_KEY` | String | Opcional (modo `auto`) | Clave de servicio para el backend. |
| `IYOK_DATA_SOURCE` | String (`nasa` \| `auto`) | Opcional (default `nasa`) | `nasa`: consulta directa a NASA sin Supabase. `auto`: usa caché y persistencia en Supabase. |
| `IYOK_ALLOW_WRITE` | Boolean (`true` \| `false`) | Opcional (default `true`) | Habilita o deshabilita escrituras/persistencia en base de datos. |
| `IYOK_WRITE_KEY` | String | Opcional | Si se define, exige `X-Iyok-Write-Key` para autorizar persistencia en Supabase. |
| `CORS_ORIGINS` | String (CSV) | Opcional | Lista de dominios autorizados separados por coma. |
