# Validación del issue #23 — 15 de noviembre de 2026

El diagnóstico original es útil para priorizar el explorador, pero sus porcentajes son estimaciones sin una medición reproducible y no acreditan cumplimiento, seguridad ni accesibilidad. Esta revisión parte del código en `a4bc771` y del servicio local observado; no acredita una revisión científica externa.

**Decisión de alcance de Manuel, 15 de noviembre de 2026:** la validación científica completa está fuera del alcance del MVP y no bloquea el cierre de este issue. Esta decisión no constituye una validación ni autoriza presentar resultados no revisados como concluyentes. Las limitaciones, el estado inconcluso y las discrepancias identificadas permanecen visibles; su resolución se mantiene como trabajo posterior.

## Ajustes al alcance

- **Tendencia:** `exploration_service.py` convierte los resultados concluyentes en inconclusos porque la corrección de dependencia temporal mostró exceso de falsos positivos en simulaciones. Véase [revisión científica](revision-cientifica-2026-11-15.md). El umbral de cinco años no garantiza una inferencia válida. Mostrar estado, método y motivo reales; no exigir pendiente, p ni significancia mientras no se revise y valide el método y sus supuestos con el responsable de datos.
- **Interpretación:** la narrativa automática requiere revisión antes de publicarse: el servicio describe el máximo y mínimo mensuales del período como un ciclo estacional, lo que no demuestra un patrón estacional, y la línea base de anomalías requiere validación. No presentar el texto como conclusión científica revisada. Mantener disponibles las advertencias reportadas por el servicio y la explicación de por qué el análisis es inconcluso.
- **Procedencia:** mostrar únicamente metadatos efectivamente devueltos para la selección: producto, fuente, resolución, ponderación, enlace y gránulos cuando existan; conservar limitaciones y advertencias. La existencia de identificadores o un DOI no acredita validación de la serie ni de la geometría.
- **1998–2000:** `snit_series.py` limita la serie SNIT a 2001–2024, aunque el código actual de catálogo utiliza el mínimo general 1998 en esa combinación. El catálogo observado en el servicio local anunció 2001–2024. La existencia de gránulos en CMR y una extracción de control no demuestra una serie 1998–2000 reprocesada con la geometría SNIT; corregir o acordar el contrato en backend antes de ampliar ese ámbito. El selector ya respeta los meses completos anunciados por la combinación seleccionada.
- **Regiones y mapa:** otras regiones del catálogo no demuestran que sus geometrías y resultados estén validados; mantener el ámbito MVP acordado hasta coordinación y verificación. El mapa es prioridad posterior y requiere geometría y capas compatibles, según `AGENTS.md`.

## Criterios actualizados

1. Mostrar el estado devuelto por la API y, para estados no concluyentes, su nota metodológica; conservar el bloqueo de inferencia mientras continúe la revisión.
2. Mostrar la procedencia disponible para la selección y las advertencias, sin sustituir valores ausentes por afirmaciones fijas.
3. Mantener el rango condicionado al catálogo de la combinación SNIT y resolver la discrepancia de 1998–2000 con backend antes de habilitarlo.
4. Revisar con backend las narrativas y la inferencia antes de mostrar conclusiones; validar supuestos, incertidumbre y comportamiento ante series incompletas.
5. Ejecutar pruebas de contrato, lint, compilación y E2E, incluyendo respuesta inconclusa, procedencia opcional, ausencia de datos y escritorio/móvil.

La aceptación del uso de la serie SNIT 2001–2024 para el MVP no equivale a validación científica de la procedencia, observaciones o tendencias. El issue puede cerrarse según la decisión de alcance de Manuel; la revisión científica, la discrepancia de cobertura y la revisión de la narrativa quedan registradas como trabajo posterior, no como tareas completadas.
