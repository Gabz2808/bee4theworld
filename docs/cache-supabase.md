# Caché de consultas NASA en Supabase

El modo `IYOK_DATA_SOURCE=auto` intenta recuperar primero una serie IMERG procesada y compatible en Supabase. Si no existe o no se puede acceder, consulta NASA CMR/Harmony y trata de guardar el resultado para consultas posteriores. El modo `nasa` conserva la consulta directa sin caché. La caché no convierte una observación en un resultado científico validado ni equivale a una exportación de Giovanni.

## Configuración

En `apps/api/.env`, ignorado por Git, configurar `IYOK_DATA_SOURCE=auto`, `EARTHDATA_TOKEN`, `SUPABASE_URL` y `SUPABASE_SECRET_KEY`. La API debe reiniciarse para leer los cambios. Mantener las claves únicamente en el servidor, fuera del navegador y de Git; el acceso MCP del agente no configura automáticamente el cliente de la API. Si Supabase no está configurado, el servicio continúa con NASA e informa en los metadatos que la caché no está disponible.

## Condiciones de reutilización

- Se usa el esquema existente `regions`, `ingestion_runs` y `processed_data`; no se cambia el esquema ni se modifican registros existentes.
- Por ahora solo se almacena la región pública `costa-rica-continental`, si existe una única región registrada y su geometría coincide con la solicitada. Los polígonos personalizados y otras regiones no se asignan a Costa Rica.
- La entrada incluye producto/versión, unidades, conversión, método, identificadores de gránulos, instantánea geométrica y marca de versión `cache-nasa-v1`. La primera versión admite `GPM_3IMERGM.07`, resolución 0,1° y unidad de origen `mm/hr`. Las ingestas previas que no usan esta marca no se reutilizan automáticamente: deben revisarse antes de migrarlas o considerarlas equivalentes.
- Se comprueba la serie completa original, incluyendo todos los meses, valores, cobertura y calidad, antes de devolver un subconjunto. Una ingesta incompleta se ignora. Los metadatos del subconjunto conservan los gránulos de la ingesta completa, que pueden incluir meses adicionales.
- Una entrada puede responder a un período incluido en ella, pero esta versión no combina varias ingestas parciales para completar un período mayor.
- `metadata.cache_status` informa `hit`, `stored`, `miss`, `unavailable` o `disabled`. `data_accessed_at` de una entrada cacheada corresponde al registro de la ingesta en Supabase, poco después de la descarga.

La escritura de la ingesta y sus meses usa dos llamadas independientes al servicio; una interrupción puede dejar un registro incompleto, pero la lectura no lo acepta como caché. Aún no hay una restricción de unicidad o una transacción compartida: solicitudes concurrentes pueden producir duplicados. No se borran registros automáticamente. La región, los datos y la metodología siguen pendientes de validación científica conjunta.

## Consultas largas

La primera consulta de un período aún puede superar los 90 segundos del proxy web. Si la API termina después, puede guardar el resultado para una consulta posterior, pero la página actual no puede seguir el progreso ni recuperar automáticamente la respuesta inicial. No repetir consultas mientras el primer trabajo continúa: el problema de trabajos largos y deduplicación se atiende en el issue #20.

## Comprobación del 14 de noviembre de 2026

Se consultó enero de 2024 desde el frontend hacia la API local con acceso al proyecto Supabase: la primera respuesta informó `stored` (20,55 s) y la segunda `hit` (0,69 s). Una lectura independiente mediante MCP confirmó una ingesta de un mes con geometría coincidente; otra consulta a NASA produjo el mismo valor y cobertura que la caché. Son tiempos de una sola prueba, no una garantía de rendimiento. Los datos y la geometría continúan pendientes de validación científica.
