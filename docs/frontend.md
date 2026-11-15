# Frontend de Iyök

Iyök se dirige inicialmente al público general. La interfaz organiza la exploración en selección, serie y evidencia; el detalle científico debe ser accesible sin ocultar las limitaciones. El [brief de experiencia](brief-experiencia.md) documenta el recorrido, los estados y la dirección natural y científica elegida; sus detalles visuales siguen abiertos.

## Estado actual

La interfaz consulta el catálogo y la exploración del backend a través de rutas del servidor Next.js. El selector de meses usa el intervalo declarado por el catálogo, que no garantiza cobertura efectiva. La respuesta se valida estructuralmente y la serie se muestra como pendiente de validación; no se presenta la interpretación estadística. La tabla incluye valores ausentes, cobertura y calidad. La correspondencia entre la región y la serie, el origen y el método siguen pendientes de revisión conjunta; no tratar esta pantalla como un resultado científico validado.

Para desarrollo, iniciar la API en `127.0.0.1:8000` y el frontend desde `apps/web` con `npm run dev`. La ruta de Next.js usa por defecto esa dirección; `IYOK_API_URL` permite configurar otra URL del backend en el servidor (ver `apps/web/.env.example`). La API necesita su propia configuración y credenciales de servidor; el acceso MCP no las configura. Nunca colocar credenciales de Supabase o Earthdata en variables públicas del frontend. Si el servicio no está disponible, la interfaz muestra un error y permite reintentar.

Para consultar NASA directamente desde el backend, ver [acceso NASA directo](acceso-nasa-directo.md). Este mecanismo usa CMR y Harmony, no Giovanni, y necesita autenticación Earthdata en el servidor.

Las rutas del frontend únicamente reenvían catálogo y exploración; no comprueban que el backend haya seleccionado la ingesta geográfica correcta. La procedencia que aparece es la declarada por el servicio, no una validación independiente de Giovanni. La validación científica sigue pendiente antes de su uso en la demo.

### Comprobación de integración — 15 de noviembre de 2026

Con escritura de caché desactivada, se consultó desde el navegador enero de 2024 para `costa-rica-continental`: el catálogo declaró 2001-01 a 2024-12 y la API devolvió HTTP 200 desde caché. La tabla mostró 66,03 mm/month, cobertura 100 % y calidad `ok`. Una consulta separada a NASA CMR/Harmony, sin caché, devolvió el mismo valor, cobertura y gránulo `G3087531387-GES_DISC` para `GPM_3IMERGM.07`. Se comprobó el estado de carga, la etiqueta de serie sin validar y la ausencia de desbordamiento horizontal en Chrome headless a 390 y 1440 píxeles. Se corrigió la visualización de una serie de un solo punto.

Esta comprobación cubre un mes, no toda la cobertura declarada. Usa la geometría aproximada provisional de la aplicación y el mismo procesamiento de la API en ambas consultas: la coincidencia no valida la geometría, el procesamiento científico ni una extracción de Giovanni. El flujo y la metodología requieren revisión con el compañero antes de presentar la serie como evidencia científica.

Una comprobación posterior procesó directamente los 288 meses de 2001–2024 para la misma geometría provisional. El cliente validó la respuesta y el navegador representó las 288 filas al servirle esa respuesta guardada; esto no fue una consulta en vivo a través del proxy. La primera consulta completa tardó más de los 90 segundos que permite el proxy, por lo que el trabajo de solicitudes largas sigue pendiente en el issue #20. El frontend informa si se agota el tiempo y advierte que el trabajo puede continuar. La serie histórica previa de Supabase difiere de la extracción directa y no está validada; véase la [revisión de datos](verificacion-datos-2026-11-15.md).

## Integración y datos

### Seguimiento del issue #8 — 15 de noviembre de 2026

Se verificó el explorador con la serie local SNIT en Chrome headless a 1280 y 390 píxeles; en escritorio se consultaron los 288 meses. Las pruebas comprueban que cambiar el período retira el resultado anterior y que los controles quedan bloqueados durante la consulta. Con respuestas modificadas solo para prueba, la tabla distingue el valor cero de un dato ausente y conserva la unidad. Manuel informó que Gabriel aceptó esta serie concreta para el MVP y los issues #7 y #8. Estas comprobaciones y la aceptación de uso no sustituyen la revisión científica de la serie y su geometría.

La [revisión técnica de la serie](revision-serie-snit-issue-8.md) contrasta la derivación de la geometría, el cálculo de los 288 valores y el efecto de la precisión de la cuadrícula; registra los puntos que requieren acuerdo con el compañero.

El compañero lidera los datos y el backend. El cliente implementado es provisional; acordar versión y rutas, catálogo y cobertura, parámetros, fechas, unidades, datos faltantes, procedencia, resultado inconcluso y errores antes de considerar aprobado el contrato. El JSON ficticio no es un contrato aprobado.

La primera variable elegida es precipitación IMERG para Costa Rica, investigada mediante Giovanni. Su [manual](https://giovanni.gsfc.nasa.gov/giovanni/doc/UsersManualworkingdocument.docx.html) describe exportación CSV de series temporales promediadas por área. Antes de mostrar una serie, acordar versión, variable exacta, área y período; registrar geometría y método de promedio, unidad, cobertura, valores faltantes, fecha de acceso y enlace al producto y a su documentación. Un rectángulo que incluye mar o países vecinos no equivale a Costa Rica. La [API de series puntuales](https://forum.earthdata.nasa.gov/viewtopic.php?p=25340&sid=8a19637cc1f2a53eb077d7a9600a4839) no sustituye un promedio regional. Validar conjuntamente la muestra y la metodología antes de comunicar tendencias.

## Próximos pasos

1. Acordar y versionar contrato y selección científica; incorporar una serie real con metadatos.
2. Confirmar la correspondencia geográfica y la procedencia, y conectar una respuesta real validada con el equipo.
3. Añadir mapa y control temporal únicamente cuando haya capas compatibles y flujo central validado.
4. Completar pruebas de integración y revisar el flujo real en escritorio y móvil; preparar demostración reproducible. El prototipo ficticio se comprobó en Chrome headless mediante Playwright a 1440 × 900 y 390 × 844.
