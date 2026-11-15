# Manual Técnico de Usuario - Iyök API (v1)

## 1. Alcance y Arquitectura de la API v1

Este manual describe la arquitectura, instalación, configuración, modelos de datos y endpoints del backend de **Iyök** (`bee4theworld`), desarrollado para el NASA Space Apps Challenge 2026 (*Challenge: Be An Earth System Trend Detective!*).

La API está construida sobre **FastAPI** y expone una superficie limpia, minimalista y estandarizada en su versión `v1`:
* **`GET /ping`**: Health check básico de disponibilidad del servicio.
* **`GET /api/v1/catalog`**: Catálogo unificado de regiones oficiales, variables climáticas activas, intervalos reales de cobertura y combinaciones disponibles.
* **`POST /api/v1/explorations`**: Motor unificado de consulta y análisis de tendencias. Soporta regiones del catálogo (`region_id`) o geometrías libres (`region`), orquesta datos satelitales (Supabase / NASA IMERG), calcula series temporales, línea base climatológica, anomalías mensuales, agregaciones anuales y evaluación estadística no paramétrica (Theil-Sen y Mann-Kendall).

> [!NOTE]
> La API no mantiene rutas obsoletas o secundarias. Toda la integración de frontend opera exclusivamente a través de los endpoints oficiales de `/api/v1/`.

---

## 2. Requisitos del Sistema

* **Python:** 3.10 o posterior (desarrollado y probado en Python 3.14).
* **Git:** Para control de versiones.
* **Supabase / PostgreSQL con PostGIS:** Para persistencia de metadatos, ejecuciones de ingesta y serie histórica de 24 años (288 meses calendario).
* **Dependencias científicas:** `fastapi`, `uvicorn`, `pydantic`, `supabase`, `pandas`, `numpy`, `scipy`, `shapely`, `pyproj`, `httpx`.

---

## 3. Instalación y Configuración del Entorno Virtual

Desde la raíz del monorepo o dentro de `apps/api/`:

### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r apps/api/requirements.txt
```

### Windows PowerShell
```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r apps/api/requirements.txt
```

---

## 4. Variables de Entorno (`.env`)

Copia la plantilla [`.env.example`](../apps/api/.env.example) a `.env` en la raíz y en `apps/api/`:
```bash
cp .env.example .env
cp .env.example apps/api/.env
```

Parámetros requeridos y opcionales:
* **`SUPABASE_URL`**: URL HTTPS del proyecto de Supabase (ej. `https://xyzcompany.supabase.co`).
* **`SUPABASE_SECRET_KEY`**: Clave privada (`service_role`) para uso exclusivo del backend en consultas y operaciones privilegiadas de base de datos.
* **`SUPABASE_PUBLISHABLE_KEY`**: Clave pública (`anon`), reservada para el cliente frontend (no se usa para operaciones de backend).
* **`SUPABASE_JWKS_URL`**: URL para validación de tokens JWT en etapas futuras.
* **`EARTHDATA_TOKEN`**: Token de autenticación de NASA Earthdata Login. Opcional para consultar la base de datos de Supabase; obligatorio si se ejecutan descargas directas en vivo de gránulos NetCDF desde NASA GES DISC / Harmony.

> [!IMPORTANT]
> El archivo `.env` está en `.gitignore` y **nunca** debe ser versionado en Git ni publicado.

---

## 5. Esquema de Base de Datos y Persistencia (`apps/api/app/init.sql`)

El esquema de base de datos relacional y geoespacial está definido en [`apps/api/app/init.sql`](../apps/api/app/init.sql). Se aplica directamente en el **SQL Editor** del dashboard de Supabase y estructura:

1. **Extensión PostGIS:** `CREATE EXTENSION IF NOT EXISTS postgis;` para cálculo espacial riguroso.
2. **Tabla `public.variables`:** Catálogo de variables (`id = 'precipitation'`, unidades `mm/month`, dataset `GPM_3IMERGM.07`).
3. **Tabla `public.regions`:** Catálogo de regiones oficiales (ej. `Costa Rica Continental` con geometría `geometry(Polygon, 4326)`, fuente `IGN/WDC`, versión `2024`).
4. **Tabla `public.ingestion_runs`:** Trazabilidad de corridas de ingesta satelital de NASA GES DISC, granularidad, rango de fechas y lista de gránulos NASA procesados.
5. **Tabla `public.processed_data`:** Almacenamiento mensual optimizado con fecha mensual (`date`), precipitación acumulada (`value`), fracción de cobertura (`coverage_fraction`), bandera de calidad (`quality_flag: 'ok' | 'partial_coverage' | 'missing_month'`), fase climática ENSO y bandera de cobertura completa.
6. **Políticas RLS e Índices:** Índices geoespaciales GIST y políticas de seguridad por filas (Row Level Security).

---

## 6. Ejecución del Servidor Backend

Con el entorno virtual activado, desde la carpeta `apps/api/`:

```bash
cd apps/api
uvicorn app.main:app --reload --env-file .env
```

*(O desde la raíz del repositorio: `PYTHONPATH=apps/api uvicorn app.main:app --reload --env-file apps/api/.env`)*

Por defecto, Uvicorn escucha en `http://127.0.0.1:8000`.

---

## 7. Especificación Detallada de Endpoints (API v1)

### `GET /ping`
Comprobación de salud básica.
* **Respuesta (`200 OK`):**
  ```json
  {
    "status": "ok"
  }
  ```

---

### `GET /api/v1/catalog`
Expone el inventario unificado de datos listos para ser consumidos por el cliente:
* Regiones disponibles y sus metadatos cartográficos.
* Variables activas, intervalo de cobertura temporal (`2001-01-01` a `2024-12-31`), resolución y restricciones de uso.
* Combinaciones válidas listas para exploración.

```bash
curl -i http://127.0.0.1:8000/api/v1/catalog
```

---

### `POST /api/v1/explorations`

Motor principal de exploración analítica. Permite solicitar la serie temporal y análisis de tendencias para un período y región determinados.

#### Reglas de Validación del Payload de Solicitud
1. **Región (`region_id` vs `region`):**
   * **Opción A (Recomendada):** Enviar `region_id` con el identificador del catálogo (ej. `"costa-rica-continental"` o UUID de Supabase). En este caso, **no** se debe enviar el objeto `region`.
   * **Opción B (Geometría libre):** Omitir `region_id` y enviar `region` como un objeto GeoJSON `Polygon` válido con coordenadas `[longitud, latitud]` en WGS84, asegurando que el polígono esté cerrado (primer y último punto idénticos).
2. **Definición del Período:**
   * Se pueden enviar las fechas en la raíz (`start_date` y `end_date`) o anidadas en el objeto `date_range` (`{ "start": "...", "end": "..." }`).
   * **Alineación obligatoria a mes completo:** `start_date` debe ser el día `01` del mes (ej. `YYYY-MM-01`) y `end_date` debe ser el último día natural del mes (ej. `YYYY-MM-31`, `YYYY-MM-30`, `YYYY-MM-28/29`).
   * **Cobertura disponible:** Las fechas deben ubicarse dentro de la serie validada de IMERG V07: `2001-01-01` a `2024-12-31`.
3. **Resolución:**
   * `temporal_resolution`: `"monthly"` (valor soportado en el MVP).
   * `variable_id`: `"precipitation"` (valor soportado en el MVP).

---

#### Ejemplos de Solicitud (JSON)

##### Ejemplo 1: Consulta Estándar del Catálogo (Recomendado para Frontend)
```json
{
  "region_id": "costa-rica-continental",
  "variable_id": "precipitation",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "temporal_resolution": "monthly"
}
```

##### Ejemplo 2: Variante con `date_range` Anidado
```json
{
  "region_id": "costa-rica-continental",
  "variable_id": "precipitation",
  "date_range": {
    "start": "2020-01-01",
    "end": "2024-12-31"
  },
  "temporal_resolution": "monthly"
}
```

##### Ejemplo 3: Polígono Personalizado GeoJSON (Área libre en mapa)
```json
{
  "region": {
    "type": "Polygon",
    "coordinates": [
      [
        [-85.0, 10.0],
        [-84.0, 10.0],
        [-84.0, 11.0],
        [-85.0, 11.0],
        [-85.0, 10.0]
      ]
    ]
  },
  "variable_id": "precipitation",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31",
  "temporal_resolution": "monthly"
}
```

---

#### Estructura de la Respuesta (`200 OK`)

La respuesta contiene cuatro bloques analíticos:

```json
{
  "status": "success",
  "metadata": {
    "variable_name": "Precipitación mensual estimada",
    "source": "NASA GES DISC / Giovanni",
    "dataset": "GPM_3IMERGM.07",
    "unit": "mm/month",
    "spatial_resolution": "0.1° (~10 km); promedio ponderado espacial",
    "temporal_resolution": "monthly",
    "selection": {
      "region_id": "costa-rica-continental",
      "region_name": "Costa Rica Continental",
      "boundary_source": "Instituto Geográfico Nacional (IGN) / WDC",
      "boundary_version": "2024",
      "requested_period": { "start": "2020-01-01", "end": "2024-12-31" },
      "effective_period": { "start": "2020-01-01", "end": "2024-12-31" }
    },
    "limitations": [
      "Estimación satelital combinada con pluviómetros; incertidumbre mayor en zonas montañosas y regímenes convectivos costeros.",
      "La serie histórica de referencia cubre 2001-2024 (24 años)."
    ],
    "warnings": []
  },
  "trend_analysis": {
    "status": "conclusive",
    "method": "Theil-Sen slope estimator + Mann-Kendall trend test",
    "slope": 19.16,
    "slope_unit": "mm/year",
    "p_value": 0.5915,
    "is_significant": false,
    "confidence_level": 0.95,
    "summary": "Tendencia no estadísticamente significativa (p >= 0.05). Pendiente estimada: +19.16 mm/año (95% de confianza).",
    "methodological_note": null
  },
  "timeseries": [
    {
      "date": "2020-01-01",
      "value": 135.42,
      "coverage_fraction": 1.0,
      "quality_flag": "ok",
      "anomaly_mm": 12.35
    }
  ],
  "annual_totals": [
    {
      "year": 2020,
      "annual_precipitation_mm": 3120.45,
      "months_reported": 12
    }
  ]
}
```

---

#### Estados del Análisis de Tendencias (`trend_analysis.status`)

El motor clasifica el veredicto estadístico de manera determinista:

| Estado | Condición de Datos | Métricas Publicadas (`slope`, `p_value`) | Nota Metodológica |
| :--- | :--- | :--- | :--- |
| **`conclusive`** | $\ge 5$ años calendario completos observados | **Sí** (`slope`, `slope_unit`, `p_value`, `is_significant`, `confidence_level`) | `null` |
| **`inconclusive`** | Entre 1 y 4 años calendario completos, o varianza cero | **No** (`null`) | Presente: Explica que la serie es insuficiente para separar variabilidad interanual de una tendencia climática. |
| **`not_computed`** | Menos de 1 año calendario completo (< 12 meses consecutivos) | **No** (`null`) | Presente: Explica que el período es menor al ciclo estacional anual mínimo. |
| **`failed`** | Ruptura o error de datos en el motor | **No** (`null`) | Presente: Detalle del fallo de cálculo. |

---

## 8. Metodología Científica y Algoritmos

### 8.1. Conversión de Tasas de IMERG a Acumulación Mensual
El producto mensual de NASA IMERG (`GPM_3IMERGM V07`) reporta la precipitación como una tasa media en $\text{mm/hr}$. La conversión a acumulación mensual en $\text{mm/mes}$ se realiza multiplicando la tasa por el número exacto de horas del mes calendario:

$$\text{Acumulación (mm)} = \text{tasa} \left(\frac{\text{mm}}{\text{hr}}\right) \times \left(\text{días del mes} \times 24.0\,\text{hr}\right)$$

Esta conversión considera de forma precisa los meses bisiestos (ej. febrero de 2020 y 2024 con 29 días = 696 horas).

### 8.2. Ponderación Espacial en Proyección de Área Equivalente
Para evitar distorsiones por convergencia de meridianos en coordenadas geográficas WGS84, la agregación espacial de celdas de cuadrícula ($0.1^\circ \times 0.1^\circ$) se calcula proyectando los polígonos a la proyección cilíndrica de igual área **EPSG:6933**.
Las celdas situadas en los límites territoriales se ponderan por la fracción exacta de área que interseca con el polígono.

### 8.3. Climatología de Referencia y Cálculo de Anomalías
Para cada mes natural $m \in \{1, \dots, 12\}$, se calcula la climatología multi-anual de referencia $\overline{P}_m$ a partir de la serie completa 2001–2024. La anomalía de cada punto temporal $t$ correspondiente al mes $m$ se calcula como:

$$\text{Anomalía}_t = P_t - \overline{P}_m$$

Una anomalía positiva indica precipitación superior a la media histórica para ese mes del año; una negativa refleja déficit pluviométrico.

### 8.4. Estimación de Tendencias (Theil-Sen y Mann-Kendall)
* **Pendiente de Theil-Sen:** Estimador no paramétrico robusto que calcula la mediana de las pendientes entre todos los pares posibles de acumulados anuales. Es resistente a valores extremos o años atípicos (como eventos intensos de El Niño / La Niña).
* **Test de Mann-Kendall:** Prueba no paramétrica para evaluar si existe una tendencia monotónica en el tiempo, ajustando por empates y calculando el p-valor exacto a dos colas mediante la distribución normal estándar. Si $p < 0.05$, la tendencia se clasifica como estadísticamente significativa al 95% de confianza.

### 8.5. Política Rigurosa para Datos Faltantes
* **Prohibición de imputación artificial:** Si un mes no cuenta con observaciones válidas, su valor se mantiene estrictamente como `null` con `quality_flag = 'missing_month'` o `'missing_value'`. **Nunca se imputa con cero**.
* **Agregación anual:** Un acumulado anual (`annual_totals`) solo se calcula si el año cuenta con los **12 meses completos** (`months_reported = 12`). Los años parciales se excluyen para no introducir sesgos artificiales en la tendencia.

---

## 9. Formato Estándar de Errores (Error Envelope)

Todos los errores HTTP devuelven un sobre estándar RFC 7807 que previene fugas de información interna y facilita el parseo en Frontend:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "La fecha de inicio 2020-01-15 debe ser el primer día de un mes (ej. YYYY-MM-01).",
    "details": []
  }
}
```

Códigos y significado:
* **400 Bad Request (`INVALID_REQUEST`):** Fechas no alineadas a mes completo, rango fuera de cobertura o fechas invertidas.
* **404 Not Found (`NOT_FOUND`):** El `region_id` o `variable_id` no existe en el catálogo.
* **422 Unprocessable Entity (`VALIDATION_ERROR`):** Geometría de polígono no cerrada, coordenadas fuera de rango o campos requeridos ausentes.
* **502 Bad Gateway (`UPSTREAM_SERVICE_ERROR`):** Problema de conexión o descarga con servicios de NASA.

---

## 10. Documentación Interactiva (Swagger / OpenAPI)

Cuando el servidor está en ejecución, se puede acceder a:
* **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
* **OpenAPI JSON:** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 11. Verificación y Suite de Pruebas Automatizadas

Con el entorno virtual activado, desde la carpeta `apps/api/`:

```bash
cd apps/api
python -m unittest discover -s tests -v
```

*(O desde la raíz del repositorio: `PYTHONPATH=apps/api python -m unittest discover -s apps/api/tests -v`)*

La suite ejecuta **50 pruebas automatizadas** que validan:
1. Modelos Pydantic v1, contratos de catálogo y exploración.
2. Rechazo de geometrías GeoJSON no cerradas o con coordenadas fuera de rango.
3. Rechazo de fechas no alineadas a inicio o fin de mes.
4. Rechazo de variables fuera del MVP.
5. Inexistencia y retorno `404` para rutas legacy eliminadas.
6. Algoritmo Theil-Sen con resistencia a outliers y cálculo de Mann-Kendall.
7. Cálculo de climatología multi-anual y anomalías preservando `null`.
8. Conexión y reutilización de cliente Supabase con credenciales del servidor.
