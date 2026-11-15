# Frontend de Iyök

Iyök se dirige inicialmente al público general. La interfaz organiza la exploración en selección, serie y evidencia; el detalle científico debe ser accesible sin ocultar las limitaciones. El [brief de experiencia](brief-experiencia.md) documenta el recorrido, los estados y la dirección natural y científica elegida; sus detalles visuales siguen abiertos.

## Estado actual

La interfaz consulta el catálogo y la exploración del backend a través de rutas del servidor Next.js. El selector de meses usa el intervalo declarado por el catálogo, que no garantiza cobertura efectiva. La respuesta se valida estructuralmente y la serie se muestra como pendiente de validación; no se presenta la interpretación estadística. La tabla incluye valores ausentes, cobertura y calidad. La correspondencia entre la región y la serie, el origen y el método siguen pendientes de revisión conjunta; no tratar esta pantalla como un resultado científico validado.

Para desarrollo, iniciar la API en `127.0.0.1:8000` y el frontend desde `apps/web` con `npm run dev`. La ruta de Next.js usa por defecto esa dirección; `IYOK_API_URL` permite configurar otra URL del backend en el servidor (ver `apps/web/.env.example`). La API necesita su propia configuración y credenciales de servidor; el acceso MCP no las configura. Nunca colocar credenciales de Supabase o Earthdata en variables públicas del frontend. Si el servicio no está disponible, la interfaz muestra un error y permite reintentar.

Para consultar NASA directamente desde el backend, ver [acceso NASA directo](acceso-nasa-directo.md). Este mecanismo usa CMR y Harmony, no Giovanni, y necesita autenticación Earthdata en el servidor.

Las rutas del frontend únicamente reenvían catálogo y exploración; no comprueban que el backend haya seleccionado la ingesta geográfica correcta. La procedencia que aparece es la declarada por el servicio, no una validación independiente de Giovanni. La respuesta de exploración real y la validación científica siguen pendientes antes de su uso en la demo.

## Integración y datos

El compañero lidera los datos y el backend. El cliente implementado es provisional; acordar versión y rutas, catálogo y cobertura, parámetros, fechas, unidades, datos faltantes, procedencia, resultado inconcluso y errores antes de considerar aprobado el contrato. El JSON ficticio no es un contrato aprobado.

La primera variable elegida es precipitación IMERG para Costa Rica, investigada mediante Giovanni. Su [manual](https://giovanni.gsfc.nasa.gov/giovanni/doc/UsersManualworkingdocument.docx.html) describe exportación CSV de series temporales promediadas por área. Antes de mostrar una serie, acordar versión, variable exacta, área y período; registrar geometría y método de promedio, unidad, cobertura, valores faltantes, fecha de acceso y enlace al producto y a su documentación. Un rectángulo que incluye mar o países vecinos no equivale a Costa Rica. La [API de series puntuales](https://forum.earthdata.nasa.gov/viewtopic.php?p=25340&sid=8a19637cc1f2a53eb077d7a9600a4839) no sustituye un promedio regional. Validar conjuntamente la muestra y la metodología antes de comunicar tendencias.

## Próximos pasos

1. Acordar y versionar contrato y selección científica; incorporar una serie real con metadatos.
2. Confirmar la correspondencia geográfica y la procedencia, y conectar una respuesta real validada con el equipo.
3. Añadir mapa y control temporal únicamente cuando haya capas compatibles y flujo central validado.
4. Completar pruebas de integración y revisar el flujo real en escritorio y móvil; preparar demostración reproducible. El prototipo ficticio se comprobó en Chrome headless mediante Playwright a 1440 × 900 y 390 × 844.
