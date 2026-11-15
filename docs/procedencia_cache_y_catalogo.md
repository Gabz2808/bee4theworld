# Procedencia Efectiva, Caché Versionada y Disponibilidad en Catálogo (Backend 5/7)

Este documento describe la especificación técnica, salvaguardas de integridad y modelo de datos implementado en el backend de Iyök para la trazabilidad rigurosa del origen satelital, persistencia en caché versionada y validación de disponibilidad en el catálogo.

---

## 1. Preservación y Exposición de la Procedencia Científica

En cumplimiento de los principios científicos de `AGENTS.md` y las directrices de trazabilidad de NASA GES DISC, cada respuesta analítica expone en `metadata` la procedencia completa del dato:

| Campo | Tipo / Ejemplo | Descripción |
| :--- | :--- | :--- |
| `effective_origin` | `"NASA Harmony"` / `"NASA Giovanni"` | Mecanismo o interfaz efectiva de extracción de datos. |
| `source` | `"NASA GES DISC mediante CMR y Harmony"` | Fuente institucional y canal de ingesta. |
| `dataset` | `"GPM_3IMERGM.07"` | Identificador formal de la colección satelital. |
| `product_version` | `"07"` | Versión de procesamiento del algoritmo IMERG (V07). |
| `processing_version`| `"1.0"` | Versión interna del flujo analítico de Iyök. |
| `doi_or_link` | `"https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07"` | Identificador persistente digital oficial del producto. |
| `source_units` | `"mm/hr"` | Unidad de tasa de precipitación original del gránulo NetCDF4. |
| `output_units` | `"mm/month"` | Unidad final de la serie tras la conversión temporal. |
| `unit_conversion` | `"Multiplicación por horas del mes calendario según año bisiesto"` | Regla física exacta empleada en la conversión. |
| `spatial_resolution` | `"0.1° (~10 km); promedio ponderado cilíndrico equivalente"` | Resolución de grilla y método de remuestreo. |
| `weighting_method` | `"Promedio espacial ponderado por área cilíndrica equivalente (EPSG:6933)"` | Proyección y cálculo de pesos de celda. |
| `source_granule_ids`| `["GPM_3IMERGM..."]` | Lista de gránulos CMR específicos que componen la serie. |
| `data_accessed_at` | `ISO 8601 Timestamp` | Momento exacto en que los datos fueron consultados o cacheados. |
| `quality_method` | `"Calibración mensual GPCC e índice de cobertura espacial mensual (umbral 70%)"` | Protocolo de control de calidad aplicado. |
| `geometry_snapshot`| `GeoJSON Polygon dict` | Fotografía de las coordenadas del polígono consultado. |

### Regla de No Atribución Falsa (Harmony vs. Giovanni)
- Cuando los datos provienen de extracción satelital en vivo mediante el conector cloud de NASA Earthdata, se etiquetan rigurosamente como **NASA Harmony**.
- **Jamás se etiqueta una extracción de Harmony como Giovanni.**
- La etiqueta de **NASA Giovanni** queda reservada de forma exclusiva a ingestas históricas precargadas (como la serie base de Costa Rica 2001-2024 en Supabase).
- Respuestas servidas desde la caché local o Supabase conservan y devuelven exactamente la procedencia original verificada.

---

## 2. Caché Versionada, Concurrencia Atómica e Invalidación

### 2.1. Clave de Caché Determinista y Versionada
La clave de caché local (`make_cache_key`) incorpora explícitamente las versiones de producto y de procesamiento:
```
{variable_id}_{product_version}_{processing_version}_{sanitized_region}_{geom_hash}_{start}_{end}.json
```
Ejemplo: `precipitation_v07_p1_costa-rica-continental_26ff0ffb5735ff88_2023-01-01_2023-12-31.json`
- Cualquier cambio de versión en el algoritmo satelital (`product_version`) o en la lógica de cálculo (`processing_version`) invalida deterministamente claves anteriores sin riesgo de servir datos obsoletos.
- El sistema mantiene compatibilidad hacia atrás con claves no versionadas preexistentes.

### 2.2. Concurrencia y Escritura Atómica
- La escritura de archivos en disco se realiza mediante un archivo temporal único por hilo/proceso (`.tmp_{pid}_{uuid}_{key}`).
- Se aplica sincronización a disco (`fsync`) y reemplazo atómico a nivel de sistema de archivos (`os.replace`).
- Esto previene colisiones entre peticiones concurrentes y descarta lecturas de archivos a medio escribir.

### 2.3. Detección y Recuperación ante Caché Incompleta
- Al invocar `load_from_cache`, se evalúa la integridad del archivo:
  - Si el JSON está truncado o corrupto, se captura la excepción, se purga el archivo del disco y se devuelve `None`.
  - Si el número de registros no coincide con el total de meses calendario esperado para el intervalo `[start, end]`, el archivo es catalogado como incompleto, se elimina y se retorna `None`.
- Esto dispara de inmediato la consulta a la fuente fresca (NASA / Supabase), garantizando auto-reparación sin intervención del usuario.

### 2.4. Invalidación Explícita
La función `invalidate_cache(variable, region, geom, start, end)` permite purgar deliberadamente entradas cacheadas específicas.

---

## 3. Catálogo Dinámico con Verificación de Disponibilidad

El endpoint `GET /api/v1/catalog` distingue con precisión la disponibilidad real de cada combinación:

1. **Intervalo Declarado (`declared_interval`):** Período nominal del catálogo IMERG (`2000-06-01` a `2024-05-31`).
2. **Disponibilidad Realmente Verificada (`verified_interval`):**
   - Para **Costa Rica Continental**: El archivo/base contiene la serie completa verificada de 288 meses (`verified_interval = [2000-06-01, 2024-05-31]`).
   - Para regiones bajo demanda (**Canal de Panamá**, **Corredor Seco**): Se verifica la presencia del token de autenticación de NASA Earthdata (`EARTHDATA_TOKEN`) o existencia de caché verificada.
3. **Estado de la Fuente (`source_status`):**
   - `"verified"`: Datos comprobados y listos para consulta inmediata.
   - `"on_demand"`: Datos satelitales obtenibles en vivo con credenciales configuradas.
   - `"source_unavailable"`: Fuente no disponible de inmediato por ausencia de credenciales en el servidor (`is_ready_for_exploration = False`).
4. **Huecos Conocidos (`known_gaps`):** Lista explícita de períodos sin cobertura dentro del intervalo. En IMERG V07 la serie mensual es continua entre junio 2000 y mayo 2024 (`known_gaps = []`).
