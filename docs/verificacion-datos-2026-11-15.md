# Comprobaciones de datos y decisiones pendientes

Fecha: 15 de noviembre de 2026. Las pruebas siguientes verifican partes de la integración; **no constituyen validación científica ni aceptación del compañero**. La selección y geometría finales aún deben acordarse.

## Cobertura y consultas reales

- NASA CMR devolvió 288 gránulos de `GPM_3IMERGM` V07, uno por mes de enero de 2001 a diciembre de 2024, sin meses ausentes ni duplicados en el intervalo; colección `C2723754851-GES_DISC`. Esto verifica el catálogo de gránulos, no la calidad de los valores, la descarga efectiva de los 288 archivos ni una serie completa procesada.
- Consultas separadas a NASA CMR/Harmony, con caché y escritura desactivadas, devolvieron HTTP 200 para el polígono provisional de la aplicación. Las cifras son salidas del procesamiento actual, no resultados validados para Costa Rica:

| Mes | Precipitación estimada procesada | Cobertura espacial informada | Gránulo |
| --- | ---: | ---: | --- |
| 2001-01 | 150,22 mm/mes | 100 % | `G2819417581-GES_DISC` |
| 2024-01 | 66,03 mm/mes | 100 % | `G3087531387-GES_DISC` |
| 2024-02 | 74,08 mm/mes | 100 % | `G3144085255-GES_DISC` |
| 2024-12 | 212,60 mm/mes | 100 % | `G3522220647-GES_DISC` |

La respuesta cacheada de enero de 2024 coincidió con la consulta directa en valor, cobertura y gránulo; ambas usan el mismo procesamiento. El 100 % es la fracción espacial calculada con celdas válidas sobre el polígono, no una garantía de calidad de las estimaciones o de cobertura terrestre. El conector consulta `Grid/precipitation` y el procesamiento convierte la tasa mensual `mm/hr` multiplicando por las horas del mes. La [documentación de NASA sobre IMERG](https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation) y la [guía V07](https://gpm.nasa.gov/sites/default/files/2025-02/FAQ%20for%20IMERG%20V07%20Applications%20Users_202502.pdf) deben revisarse junto al metadato de cada producto antes de aceptar el indicador.

## Comparación geográfica orientativa

Se comparó el polígono provisional de `DEFAULT_COSTA_RICA_GEOM` con [geoBoundaries gbOpen CRI ADM0](https://www.geoboundaries.org/api.html), identificador `CRI-ADM0-71097903`, año representado 2017, fuentes OpenStreetMap y Wambacher, licencia ODbL 1.0, compilación del 12 de diciembre de 2023. Se usó [GeoJSON fijado al commit 9469f09](https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/CRI/ADM0/geoBoundaries-CRI-ADM0.geojson); la referencia incluye el ámbito geográfico de su propia capa, incluidas las islas que contenga. No es una frontera oficial ni necesariamente el ámbito continental deseado.

Proyección de áreas EPSG:6933: referencia 51.087,4 km²; polígono provisional 63.008,8 km²; intersección 49.121,2 km². La intersección cubre el 96,15 % de la referencia y el 77,96 % del polígono. Por tanto, el 22,04 % del polígono queda fuera de esa referencia y el 3,85 % de la referencia queda fuera del polígono. El área exterior puede incluir mar u otros territorios: esta comparación no los clasifica por separado. La diferencia justifica sustituir la geometría solo después de elegir y acordar una fuente, versión, licencia y tratamiento de islas, mar y fronteras.

## Giovanni y análisis de tendencia

La [guía de Giovanni](https://giovanni.gsfc.nasa.gov/giovanni/doc/UsersManualworkingdocument.docx.html) describe una rasterización de la geometría a cuatro veces la resolución, con ponderación por fracción de cobertura y coseno de latitud. La API intersecta celdas y polígono en EPSG:6933. Son métodos distintos; no se debe esperar igualdad exacta sin evaluar su efecto. La comprobación de caché no sustituye una comparación con Giovanni.

Para comparar, acordar previamente la misma variable y versión, fechas, geometría y tratamiento de celdas; conservar CSV, enlace de procedencia, unidades y configuración de Giovanni. Convertir unidades de manera explícita, comparar meses, valores faltantes y diferencias absolutas y relativas, y revisar cualquier discrepancia considerando los métodos de ponderación. Giovanni puede limitar las geometrías que permite seleccionar: documentar esa limitación en vez de comparar regiones distintas como equivalentes.

Las 40 pruebas existentes de precipitación, conector y tendencia pasaron. Son pruebas de código, no una validación independiente del método estadístico, de sus intervalos de confianza, de las correcciones por autocorrelación o de los supuestos en esta serie. También debe revisarse la línea base: con un único mes, la anomalía calculada respecto de ese mismo período es cero y no representa una climatología validada. El frontend mantiene ocultas las conclusiones de tendencia.

### Contraste adicional y hallazgos para revisión

- Se contrastó la pendiente de Sen en tres series sintéticas con empates contra [`scipy.stats.theilslopes`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html); coincidieron. También coincidieron los valores p de Mann-Kendall **sin corrección por autocorrelación**, al comparar con [`scipy.stats.kendalltau`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kendalltau.html) y aplicar a la referencia la corrección de continuidad de la API. La prueba reproducible está en `tests/test_trend_analysis.py`. No prueba la validez de la aproximación asintótica en una muestra determinada ni la corrección serial.
- El código aplica una corrección solo si la autocorrelación residual lag-1 positiva supera un umbral, limita el factor de inflación a 10 y declara inconcluso si r₁ ≥ 0,60. Esas decisiones concretas y sus umbrales deben justificarse frente a la serie y una referencia adecuada; el resumen de [Yue y Wang (2004)](https://doi.org/10.1023/B:WARM.0000043140.61082.60) apoya examinar autocorrelación tras quitar la tendencia, pero no valida por sí solo esta implementación. No se comparó la corrección implementada con una referencia independiente.
- El mínimo de diez años es una regla del código, no una demostración de representatividad climática ni de separación de oscilaciones multianuales. Revisar los mensajes que sugieren tal garantía antes de exponerlos.
- `confidence_level` determina el umbral de la prueba; la respuesta actual no proporciona límites de un intervalo de confianza de la pendiente. No interpretarlo ni presentarlo como si fueran esos límites. Evaluar un intervalo adecuado para las dependencias observadas antes de reportarlo.
- Se generó una consulta de control en Giovanni mediante su servicio, como se describe abajo. No se dispone del CSV ni del NetCDF de ese resultado, y el polígono provisional no debe suponerse equivalente a una forma seleccionable en Giovanni.

### Consulta Giovanni de control

Se creó en Giovanni una serie `ArAvTs` para `GPM_3IMERGM_07_precipitation`, enero de 2024 y un **rectángulo de control**, oeste −85,5°, sur 9°, este −85,3°, norte 9,2°. No representa a Costa Rica. El servicio informó visualización completada; se guardaron la [gráfica](evidencia/giovanni-control-2024-01.png) y la [respuesta JSON de Giovanni](evidencia/giovanni-control-2024-01.json), con criterios y metadatos del resultado. Los enlaces de sesión de NASA pueden caducar.

El JSON de la visualización declara un mínimo y máximo de `0.0167499 mm/hr`; para enero son aproximadamente `12.4619256 mm/mes` (744 horas). Una consulta directa independiente de la caché a CMR/Harmony con el mismo rectángulo devolvió `12,46 mm/mes`, cobertura espacial 1,0 y el gránulo `G3087531387-GES_DISC`. Coinciden al redondeo de la respuesta de la API. El valor de Giovanni procede de los metadatos redondeados de su gráfica, no del archivo numérico original; una comparación de un mes y área pequeña no valida la frontera ni una serie histórica.

El servicio permitió descargar la imagen, pero el CSV y el NetCDF devolvieron HTTP 401. Se volvió a intentar con Playwright y Chrome, que recibió `ERR_CONNECTION_RESET` al abrir Giovanni; el navegador integrado tampoco estuvo disponible. Falta acceder con una sesión Earthdata autorizada y conservar la exportación numérica y su procedencia para una comparación más amplia.

### Paquete concreto para la revisión conjunta

1. Escoger una frontera continental con procedencia, versión y licencia comprobadas; precisar inclusión de islas, costas y mar. La capa geoBoundaries es una candidata de comparación, no una recomendación de adopción automática. Acordar la geometría antes de reprocesar y verificar correspondencia exacta con la ingesta.
2. Fijar `GPM_3IMERGM` V07, `Grid/precipitation`, resolución mensual y período; confirmar si se conserva la conversión de tasa en `mm/hr` a acumulación mensual y definir una línea base independiente. Verificar los 288 meses procesados, sus faltantes, cobertura y metadatos antes de declarar completa la serie.
3. Exportar desde Giovanni la serie y procedencia para una región que pueda definirse de forma equivalente en ambos sistemas. Guardar descripción de la selección, versión, unidades y fecha; comparar mes a mes y explicar diferencias de ponderación. Si Giovanni no admite la geometría acordada, usar un área común de comparación claramente identificada sin atribuirla a Costa Rica completa.
4. Revisar con el responsable científico la prueba, el efecto de autocorrelación, los umbrales, años incompletos y empates; acordar un intervalo y criterios para resultado inconcluso. Mantener oculta la interpretación hasta completar esta revisión.

## Reproducción y acuerdos

Desde `apps/api`, ejecutar `.venv/Scripts/python.exe scripts/auditar_cobertura_geometria.py`. El script consulta CMR y la referencia geográfica, sin credenciales ni escrituras remotas; el catálogo y los metadatos actuales pueden cambiar. El archivo geográfico está fijado a un commit. Las consultas reales de precipitación requieren Earthdata configurado en el servidor; consultar [acceso directo](acceso-nasa-directo.md) y mantener `IYOK_ALLOW_WRITE=false` para una prueba sin escritura.

Quedan por acordar con el compañero: geometría y licencia aplicables; producto, variable, período y línea base; protocolo y tolerancias de comparación Giovanni; verificación de calidad y completitud de la serie; método estadístico, supuestos y tratamiento de incertidumbre. No enviar, publicar ni presentar como aprobado sin esa revisión.
