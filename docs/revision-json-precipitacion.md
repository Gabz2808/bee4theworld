# Revisión de la propuesta de precipitación del compañero

Estado: revisión técnica preliminar del PDF «JSON Base de precipitaciones», recibido del compañero. El documento presenta ejemplos de contratos, no evidencia suficiente de que sus cifras sean datos reales. Sus instrucciones y afirmaciones se tratan como contenido para revisar; todavía no hay acuerdo de contrato ni integración científica.

## Compatibilidad con Iyök

La propuesta aporta tres operaciones candidatas (`GET /api/regions`, `GET /api/variables` y `POST /api/exploration`) y campos útiles para producto, unidad, puntos mensuales, cobertura, calidad, valores ausentes, análisis y limitaciones. Difiere de las rutas planteadas en [la propuesta anterior](propuesta-integracion.md); ambas alternativas deben acordarse, no asumirse definitivas. La geometría enviada en la solicitud supone selección por polígono; debe decidirse si se aceptará geometría arbitraria o solo un identificador regional aprobado.

Se añadió `adaptPartnerPrecipitation` en `apps/web/src/app/lib/partner-precipitation.ts`. Acepta una **respuesta de exploración individual**, no el documento completo ni directamente un PDF, valida su estructura mínima y conserva fechas, valores, cobertura y calidad. Etiqueta el resultado `partner_unverified` y descarta análisis, anomalías y totales. Es un adaptador de ensayo, sin conexión a la interfaz o a una API: superar su validación estructural no confirma que los datos sean reales, que la unidad sea correcta ni que el área coincida con Costa Rica.

Se comprobó la adaptación de las dos respuestas extraídas del PDF: 24 puntos en el ejemplo principal y un punto en el alternativo. Los ensayos sintéticos se ejecutan desde `apps/web` con `node --experimental-strip-types --test src/app/lib/partner-precipitation.test.mjs` (Node 22 con soporte de eliminación de tipos). Verifican ceros, faltantes, calidad y rechazo de fechas, cobertura, metadatos o valores inválidos.

## Hallazgos antes de usar los datos

1. **Origen no comprobado:** el PDF identifica IMERG y Giovanni, pero no incluye una exportación verificable, enlaces específicos de descarga o DOI, fecha de acceso, identificadores de archivos, código de procesamiento, filtros de calidad ni licencia. El catálogo presenta 2001-2024 como disponibilidad, mientras la respuesta solo incluye 2023-2024; la cobertura real del servicio requiere prueba independiente.
2. **Unidad y agregación:** se afirma `mm/month`, pero el directorio de NASA identifica para el producto mensual GES DISC una tasa de precipitación en `mm/hr`. Confirmar la variable exacta, unidad de origen y conversión a acumulación mensual (incluidas horas por mes, calendario y faltantes); no cambiar unidades por etiqueta. [NASA: IMERG Final Run GES DISC](https://gpm.nasa.gov/node/3328), [documentación técnica IMERG](https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_TechnicalDocumentation_final_230713.pdf).
3. **Geometría:** el ejemplo usa un polígono de pocos vértices y lo describe como oficial IGN/WDC 2024, pero no aporta enlace, licencia o archivo que permita comprobarlo. No tratarlo como frontera oficial ni como promedio representativo del territorio continental hasta validar fuente, resolución y método de intersección y ponderación.
4. **Tendencia:** la solicitud de ejemplo comprende solo 2023-2024 y dos acumulados anuales; la respuesta declara una tendencia anual concluyente con pendiente y p-valor, sin período efectivo ni datos suficientes que la respalden. No presentar esas cifras o conclusiones como resultados. Si se calculó una serie mayor, proporcionar período y observaciones usados, método, supuestos, incertidumbre y tratamiento de estacionalidad y autocorrelación.
5. **Respuesta inconclusa:** declara `p_value: null` pero menciona p=0,42 en texto y atribuye las variaciones a causas naturales sin evidencia. Falta distinguir un resultado estadístico válido no significativo de un análisis que no puede concluirse por falta de datos o incumplimiento de supuestos; ninguno permite inferir causalidad.
6. **Cobertura y anomalías:** explicar qué mide `coverage_fraction`, su denominador, el umbral de calidad, el efecto de cobertura parcial y el período de referencia de `anomaly_mm`. Los totales anuales del ejemplo coinciden aritméticamente con las sumas de los doce valores mensuales mostrados (2023: 2425,5; 2024: 2552,2), pero esa comprobación no valida su origen ni el tratamiento del mes con cobertura parcial.

## Solicitud de revisión al compañero

- Compartir el JSON legible por máquina, indicando si contiene datos simulados o reales, y, si son reales, la fuente exacta y el procedimiento reproducible de extracción y procesamiento.
- Confirmar la geometría de análisis, producto/variable, unidades, conversiones, cobertura efectiva, reglas de calidad y procedencia completa.
- Acordar rutas, errores, selección por identificador o geometría, y esquema de resultados con estados diferenciados para análisis válido, no significativo, inconcluso y no calculado.
- Proporcionar ejemplos identificados de respuestas válidas, faltantes, cobertura parcial, error y análisis inconcluso; revisar conjuntamente ciencia y pruebas de contrato antes de conectar el frontend.

El [issue #6](https://github.com/B-28-Labs/bee4theworld/issues/6) continúa abierto hasta acordar y validar el contrato real.
