# Revisión de la respuesta técnica de backend

Fecha de revisión: 14 de noviembre de 2026\. Fuente: PDF «\_respuesta técnica detallada a consultas a backend», recibido del equipo. Las afirmaciones sobre una implementación o un acuerdo son declaraciones del documento; esta revisión no las convierte por sí solas en verificaciones del código ni en aprobación del contrato.

## Resultado

La respuesta resuelve varias preguntas de diseño y aporta una base concreta para integrar. La disponibilidad en el catálogo de NASA y la aritmética de conversión se pudieron contrastar. La fórmula espacial publicada y la regla estadística de cinco años requieren corrección o justificación antes de presentar resultados científicos. El issue \#6 debe continuar abierto hasta revisar la implementación real, acordar las correcciones y probar el cliente contra el contrato efectivo.

## Lo que se pudo comprobar

1. **Colección y gránulos.** Una consulta pública a CMR de la colección `C2723754851-GES_DISC` con `temporal=2001-01-01T00:00:00Z,2024-12-31T23:59:59Z` devolvió 288 entradas con 288 meses únicos, desde 2001-01 hasta 2024-12; el identificador `G3087531387-GES_DISC` figura entre ellas. Esto verifica el catálogo consultado, no la descarga, integridad, calidad o procesamiento de esos archivos en Supabase. [Directorio CMR](https://cmr.earthdata.nasa.gov/search/site/collections/directory/GES_DISC/gov.nasa.eosdis), [documentación de búsqueda CMR](https://cmr.earthdata.nasa.gov/search/site/docs/search/api.html).  
2. **Unidades.** Para una tasa media mensual efectivamente expresada en `mm/hr`, multiplicar por las horas del mes produce una acumulación expresada en mm para ese mes. Los factores 744, 720, 696 y 672 son correctos para 31, 30, 29 y 28 días respectivamente. Esto presupone que el valor es la tasa media representativa del intervalo completo y que las fechas, unidades y datos faltantes se manejan correctamente. NASA identifica el producto mensual y la tasa de precipitación; debe verificarse el nombre y la unidad en el archivo concreto. [NASA GPM](https://gpm.nasa.gov/node/3328), [documentación técnica IMERG](https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_TechnicalDocumentation_final_230713.pdf).  
3. **Proyección y método.** EPSG:6933 es una proyección cilíndrica de área equivalente, apropiada para calcular áreas dentro de su ámbito. Recortar celdas contra la región es una estrategia razonable, si se reproyectan correctamente, se preservan los bordes de celda y se calcula el área de intersección. Esto no demuestra que se haya usado la frontera oficial ni que el código lo haga. [NSIDC: guía EASE-Grid](https://nsidc.org/data/user-resources/help-center/guide-ease-grids).  
4. **Campos de integración.** Las rutas v1, las fechas explícitas, los estados y el sobre de error propuestos son compatibles en principio con el flujo de Iyök. El documento contiene una petición, pero no un catálogo y una respuesta de éxito completos y ejecutables, ni un esquema formal de errores y tipos; tampoco prueba que exista un servidor accesible.

## Cuestiones que deben resolverse

### Peso espacial y cobertura

El documento define `w_i = área(intersección) / área(celda)` y después calcula `sum(w_i * P_i) / sum(w_i)`. Eso pondera por **fracción de celda**, no necesariamente por **área territorial**: las celdas de 0,1° en longitud/latitud tienen áreas distintas según latitud, incluso al proyectarlas para medirlas. Para una media por área, usar `a_i = área(celda_i ∩ región)` y `sum(a_i * P_i) / sum(a_i)` sobre celdas válidas. De forma equivalente, puede emplearse `w_i * área(celda_i)`.

Ejemplo ilustrativo: dos celdas completamente cubiertas con áreas 1 y 2, y valores 0 y 100, producen 50 con pesos de fracción iguales, pero 66,67 con pesos de área. Aplicar el mismo criterio a la cobertura: `sum(a_i válidas) / sum(a_i totales)`. La diferencia real en Costa Rica debe medirse con la geometría y la malla reales; no se afirma que el código ya tenga el error, solo que la fórmula del PDF lo presenta.

### Inferencia estadística

No puede darse por válida una regla general `>=5 años => conclusive`. Cinco años completos son un umbral de producto propuesto, no una garantía de representatividad climática, potencia suficiente ni validez de supuestos. La corrección de empates no corrige autocorrelación; documentar la prueba para muestras pequeñas, la dependencia temporal, los años incompletos y el tratamiento de cambios de sensores. USGS explica que la correlación serial puede afectar el nivel y el resultado de Mann-Kendall. [USGS: métodos estadísticos](https://pubs.usgs.gov/tm/04/a03/tm4a3.pdf), [USGS: dependencia serial](https://pubs.usgs.gov/sir/2004/5080/pdf/sir20045080.pdf).

Un resultado `p >= 0,05` significa que no se rechaza la hipótesis nula con el umbral y método elegidos; no demuestra ausencia de tendencia ni identifica «variabilidad natural» como causa. Conviene separar validez del análisis (`computed`, `inconclusive`, `not_computed`) de significancia, y explicar los límites sin causalidad. Acordar intervalos de confianza o justificar su ausencia. También precisar cómo se cuentan años completos cuando se solicitan meses parciales, faltantes y discontinuidades.

### Trazabilidad, estados y contrato

- Solicitar acceso de lectura al código o revisión del PR, esquema OpenAPI y una URL de desarrollo o respuestas reales sanitizadas. El repositorio consultado solo mostraba `main` y `apps/api/requirements-lock.txt`; no se verificaron rutas, ingesta, cálculos ni persistencia en Supabase. El UUID de ingesta es una pista, no evidencia independiente de su contenido.  
- Obtener la fuente y versión efectiva de la frontera, enlace, licencia, hash o instantánea, exclusión de islas, CRS, malla y prueba de reproducibilidad. La procedencia IGN/WDC 2024 sigue sin verificarse.  
- Definir denominador espacial y temporal, máscaras, umbral mínimo de cobertura, consistencia entre `quality_flag`, `value` y `coverage_fraction`, y reglas para totales anuales. Exigir 12 meses nominales no basta si un mes tiene cobertura espacial parcial.  
- Acordar período de referencia de anomalías, su cobertura y tratamiento de datos faltantes; no asumir que una media sobre cualquier intervalo es una climatología válida.  
- El ejemplo de error del PDF incluye `//` dentro de un bloque etiquetado JSON; esos comentarios no son JSON válido. Entregar ejemplos legibles por máquina separados por caso, con códigos y HTTP coherentes.  
- Definir contrato versionado completo: obligatoriedad de campos, unidades, inclusión de fechas, intervalos disponibles y huecos, estados, datos faltantes, errores, compatibilidad, autenticación y CORS; incluir éxito, sin cobertura, datos parciales, error y resultado inconcluso. Confirmar que toda selección marcada como lista corresponde a datos disponibles y validados.

## Siguiente paso

Pedir al equipo de backend los artefactos verificables y contrastar una respuesta real completa con el contrato y las pruebas de integración. El adaptador actual `partner_unverified` corresponde al ejemplo anterior y no debe tratarse como cliente v1 ni como prueba de compatibilidad del backend reportado.