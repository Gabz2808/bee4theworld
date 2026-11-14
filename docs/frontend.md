# Frontend de Iyök

Iyök se dirige inicialmente al público general. La interfaz organiza la exploración en selección, serie y evidencia; el detalle científico debe ser accesible sin ocultar las limitaciones. El [brief de experiencia](brief-experiencia.md) documenta el recorrido, los estados y la dirección natural y científica elegida; sus detalles visuales siguen abiertos.

## Estado actual

La pantalla presenta una serie sintética sin unidades físicas, explícitamente identificada como demostración. No hay análisis estadístico ni conexión a datos NASA. La fuente de ejemplo está aislada en `apps/web/src/app/lib/exploration.ts`; su tipo es interno y no constituye un contrato de API. Los selectores están deshabilitados hasta conocer la cobertura real. La tabla ofrece una alternativa a la gráfica, incluidos valores ausentes.

## Integración y datos

El compañero lidera los datos y el backend. Acordar antes de implementar el cliente: versión y rutas, catálogo y cobertura, parámetros, fechas, unidades, datos faltantes, procedencia, resultado inconcluso y errores. Evitar adaptar el JSON ficticio como si fuera contrato aprobado.

La primera variable elegida es precipitación IMERG para Costa Rica, investigada mediante Giovanni. Su [manual](https://giovanni.gsfc.nasa.gov/giovanni/doc/UsersManualworkingdocument.docx.html) describe exportación CSV de series temporales promediadas por área. Antes de mostrar una serie, acordar versión, variable exacta, área y período; registrar geometría y método de promedio, unidad, cobertura, valores faltantes, fecha de acceso y enlace al producto y a su documentación. Un rectángulo que incluye mar o países vecinos no equivale a Costa Rica. La [API de series puntuales](https://forum.earthdata.nasa.gov/viewtopic.php?p=25340&sid=8a19637cc1f2a53eb077d7a9600a4839) no sustituye un promedio regional. Validar conjuntamente la muestra y la metodología antes de comunicar tendencias.

## Próximos pasos

1. Acordar y versionar contrato y selección científica; incorporar una serie real con metadatos.
2. Implementar controles conectados, estados de carga/error y visualización de resultados y evidencia reales.
3. Añadir mapa y control temporal únicamente cuando haya capas compatibles y flujo central validado.
4. Completar pruebas de integración y revisar el flujo real en escritorio y móvil; preparar demostración reproducible. El prototipo ficticio se comprobó en Chrome headless mediante Playwright a 1440 × 900 y 390 × 844.
