# Contrato de integración v1 para el MVP

Estado: **alcance operativo del primer caso**, registrado tras la revisión frontend–backend en [coordinación](../apps/api/COORDINACION_FRONTEND_BACKEND.md) y la instrucción de Manuel de continuar con la integración. La respuesta del agente de backend describe las rutas y estructuras v1; este documento precisa el subconjunto que consume frontend, sin atribuirle una aprobación explícita de cada detalle. El OpenAPI de la API en `/openapi.json` describe el esquema implementado. Cambios incompatibles requieren coordinación entre ambos equipos.

## Operaciones y selección

| Operación | Solicitud y comportamiento |
| --- | --- |
| `GET /api/v1/catalog` | Devuelve `status`, regiones, variables y combinaciones, con identificadores, intervalo y resolución. El catálogo es declarativo: una opción no acredita por sí sola que la serie esté disponible o validada. |
| `POST /api/v1/explorations` | El frontend envía `region_id`, `variable_id`, `start_date`, `end_date` y `temporal_resolution`. Para el MVP usa `costa-rica-continental`, `precipitation` y `monthly`. Las fechas son inclusivas y abarcan meses completos. |

El backend admite también geometría directa y `date_range`; el cliente del MVP no utiliza esas variantes. El rango actualmente habilitado por el backend es 2001-01-01 a 2024-12-31. NASA CMR contiene meses anteriores, pero no están habilitados aún en la API.

## Respuesta y validación del cliente

- Una respuesta exitosa incluye `metadata`, `timeseries`, `trend_analysis` y `annual_totals`; `interpretation` es opcional y el frontend no la presenta mientras se revisa el método científico.
- Los metadatos identifican fuente declarada, producto, unidad, resolución, selección, limitaciones y advertencias. Una consulta directa a NASA añade unidad original, conversión, método espacial, gránulos y fecha de acceso. Estos campos describen lo reportado por el servicio; no constituyen validación independiente de los datos.
- Cada punto mensual lleva fecha de inicio, valor finito no negativo o `null`, fracción de cobertura de 0 a 1 y etiqueta de calidad. El cliente exige meses únicos, ordenados y completos en el rango solicitado; los faltantes deben figurar explícitamente, no como cero.
- El cliente exige que `region_id` de respuesta coincida con el solicitado y que períodos solicitado y efectivo coincidan. El modo directo NASA actualmente cumple este subconjunto; si una vía devuelve un UUID distinto del identificador público, el cliente rechaza la respuesta hasta acordar un mapeo verificable.
- Los estados admitidos para análisis son `conclusive`, `inconclusive` y `not_computed`. El cliente valida la estructura, pero no presenta la conclusión estadística: longitud de serie, dependencia temporal, calidad y supuestos siguen requiriendo revisión.
- Los errores usan un objeto `error` con `code`, `message` y `details`. El cliente distingue error HTTP, fallo de red y respuesta incompatible, sin mostrar detalles internos. `NASA_AUTH_REQUIRED` indica que falta configurar Earthdata en el servidor.

## Conexión, pruebas y límites

El navegador llama al servidor Next.js en `/api/backend/catalog` y `/api/backend/explorations`; este reenvía exclusivamente a las rutas v1 del backend configurado. No hay credenciales en el cliente. El modo predeterminado `auto` intenta usar la [caché compatible en Supabase](cache-supabase.md) y consulta NASA CMR/Harmony si no hay entrada; `nasa` consulta directamente. El mecanismo de acceso no es Giovanni y no debe etiquetarse como tal. Los metadatos incluyen `cache_status` para informar el resultado de la caché.

Se probó el cliente desacoplado con ejemplos sintéticos de catálogo, éxito, faltantes, cobertura parcial, error, respuesta incompatible y análisis inconcluso. También consultó a través de Next.js una exploración real de NASA de enero de 2024 y recibió un punto con estado `not_computed`. Los datos reales y la geometría aproximada siguen pendientes de validación científica. Los issues #7–#10 mantienen los trabajos de cobertura, visualización, interpretación y caso real; este contrato no los cierra.
