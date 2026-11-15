# Iyök - Tablero de Tareas Backend (GitHub Projects)

Este documento contiene la división de tareas para el desarrollo del backend de Iyök utilizando **Python, FastAPI, Supabase y Pandas/SciPy**. Está diseñado para implementarse con la asistencia de GitHub Copilot.

> **Actualización del 15 de noviembre:** el checklist siguiente es histórico y registra implementación informada, no aceptación científica ni cierre de issues. La geometría es provisional; la ingesta histórica y la extracción NASA directa difieren y su procedencia no está resuelta. Los issues backend #15–#21 permanecen abiertos. Para instrucciones y evidencia vigentes, leer primero el [traspaso de coordinación](../apps/api/COORDINACION_FRONTEND_BACKEND.md) y la [verificación de datos](verificacion-datos-2026-11-15.md).

## Checklist de estado (14 de noviembre de 2026)

### Implementado

- [x] **BE-01:** Dependencias y entorno virtual configurados en Python con `requirements.txt`.
- [x] **BE-02:** Estructura modular FastAPI y health check en `GET /ping`.
- [x] **BE-03:** Proyecto Supabase conectado; cliente de backend implementado con `SUPABASE_URL` y `SUPABASE_SECRET_KEY` en `.env`.
- [x] **BE-04:** Esquema de base de datos relacional y geoespacial `app/init.sql` aplicado y verificado en Supabase remoto. Extensión PostGIS, tablas (`regions`, `variables`, `ingestion_runs`, `processed_data`) e índices funcionando; región `Costa Rica Continental` sembrada con geometría PostGIS **provisional, sin fuente oficial validada**.
- [x] **BE-05:** Modelos Pydantic para los contratos v1 acordados; pruebas de validación rigurosas para polígonos GeoJSON y fechas.
- [x] **BE-06:** Existe una ingesta histórica con 288 meses continuos en Supabase. Su trazabilidad y valores **requieren revisión**: los identificadores no coinciden con CMR y los valores difieren de la extracción directa; ver la actualización anterior.
- [x] **BE-07:** Preparación y normalización mensual con meses faltantes, cobertura espacial y banderas de calidad (`ok`, `partial_coverage`, `missing_month`).
- [x] **BE-08:** Cálculo de línea base mensual climatológica y anomalías (`anomaly_mm`) implementado en `app/services/trend_analysis.py`.
- [x] **BE-09:** Estimación de tendencia robusta (pendiente de Theil-Sen) y regresión OLS implementada.
- [x] **BE-10:** Prueba de significancia estadística Mann-Kendall con ajuste de empates y generación de veredicto formal `TrendAnalysis` con 4 estados (`conclusive`, `inconclusive`, `not_computed`, `failed`).
- [x] **BE-11:** Integración del flujo unificado en `POST /api/v1/explorations` conectando datos reales de Supabase, línea base/anomalías, totales anuales y motor de tendencias, con soporte para `region_id` o polígono personalizado.
- [x] **BE-12:** Manejo estandarizado de errores HTTP (400, 404, 422, 502) mediante sobres de error `{error: {code, message, details}}`.
- [x] **BE-13:** Endpoints documentados en Swagger/OpenAPI (`GET /ping`, `GET /api/v1/catalog`, `POST /api/v1/explorations`). Rutas legacy eliminadas. La suite ejecutada con `python -m unittest discover -s tests -v` cuenta con **50 pruebas pasando al 100%**.

### Estado general de tareas

- Las marcas de implementación no implican que todas las tareas estén verificadas o cerradas: revisar los issues abiertos y los resultados de la comprobación posterior.

### Decisiones y acuerdos implementados

- [x] Conexión real de backend a Supabase verificada sin exponer `SUPABASE_SECRET_KEY`.
- [ ] Validar procedencia, licencia y representación del polígono continental registrado en PostGIS; la etiqueta histórica `2024` no demuestra que sea oficial.
- [x] Adoptada la propuesta conjunta frontend-backend (Borrador 0.1, Issue #6): rutas `/api/v1/catalog` y `/api/v1/explorations` con `region_id`, sobre de errores seguro y separación estricta de responsabilidades científicas.
- [x] Eliminación de rutas secundarias/legacy para mantener una superficie API limpia.
- [x] Contrato `iyok_api_contracts_mock.json` y modelos afinados a v1: catálogo unificado, precipitación IMERG mensual, serie con `anomaly_mm`, totales anuales y variantes concluyente, inconclusa y no calculada.

---

## Epic 1: Configuración Base y Entorno (Sprint 1)

- [x] **[BE-01] Inicializar repositorio y entorno virtual:** Configurar el repositorio en GitHub, crear el entorno virtual de Python (`venv`), e inicializar el archivo `requirements.txt` con las dependencias base (`fastapi`, `uvicorn`, `pandas`, `pydantic`, `supabase`, `shapely`, `pyproj`).
- [x] **[BE-02] Estructurar el proyecto FastAPI:** Crear la estructura de carpetas modular (`app/api`, `app/core`, `app/models`, `app/services`) y levantar el servidor base con un endpoint de health check (`GET /ping`).
- [x] **[BE-03] Configuración de Supabase:** Usar el proyecto Supabase existente, configurar `SUPABASE_URL` y `SUPABASE_SECRET_KEY` en `.env`, y crear el cliente de Supabase para FastAPI en `app/core/supabase_client.py`.

## Epic 2: Base de Datos y Modelos (Sprint 1-2)

- [x] **[BE-04] Diseñar esquema en Supabase (PostGIS):** Crear y aplicar esquema SQL `app/init.sql` para `regions`, `variables`, `ingestion_runs` y `processed_data`, habilitar extensión PostGIS y configurar RLS/accesos.
- [x] **[BE-05] Implementar modelos Pydantic:** Definir los esquemas de validación de datos de entrada (validación de polígonos GeoJSON y fechas) y de salida, basándose estrictamente en los contratos acordados.

## Epic 3: Ingesta y Procesamiento de Datos (Sprint 2-3)

- [x] **[BE-06] Ingesta GPM IMERG Final V07:** Consultar `GPM_3IMERGM` mensual para precipitación; verificar los gránulos con CMR y persistir la serie histórica completa de 288 meses (2001-2024) en Supabase con trazabilidad.
- [x] **[BE-07] Limpieza y agregación temporal (Pandas):** Normalizar la serie mensual, explicitar meses faltantes y cobertura espacial, y validar valores; conservar extremos de precipitación.

## Epic 4: Motor Analítico y Estadístico (Sprint 3)

- [x] **[BE-08] Implementar cálculo de línea base y anomalías:** Programar la lógica matemática con Pandas/NumPy para calcular el promedio histórico mensual (2001-2024) y la desviación (anomalía en mm) de cada punto en el tiempo respecto a ese promedio.
- [x] **[BE-09] Desarrollar análisis de tendencias:** Integrar estimador Theil-Sen (Sen's slope) y regresión OLS para calcular la tasa de cambio (`slope`, `slope_unit`) de la serie temporal anual.
- [x] **[BE-10] Implementar prueba de significancia:** Aplicar la prueba estadística de Mann-Kendall con corrección de empates para calcular el valor _p_ (`p_value`) y clasificar el veredicto en `conclusive`, `inconclusive` o `not_computed`.

## Epic 5: Endpoints y Entrega (Sprint 4)

- [x] **[BE-11] Integrar flujo en `POST /api/v1/explorations`:** Conectar el endpoint principal, de manera que reciba el payload, consulte Supabase (o la NASA si no hay caché), pase por el motor estadístico y devuelva el JSON completo.
- [x] **[BE-12] Manejo de errores y validaciones HTTP:** Implementar excepciones de FastAPI para manejar casos de polígonos inválidos, fechas incongruentes o errores en upstream.
- [x] **[BE-13] Pulir documentación interactiva (Swagger) y manual técnico:** Asegurar que Swagger UI y el manual técnico reflejen los modelos Pydantic correctos, reglas de fechas, ejemplos prácticos y verificación con 50 pruebas automatizadas.
