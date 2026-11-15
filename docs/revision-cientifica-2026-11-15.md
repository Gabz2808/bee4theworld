# Revisión científica reproducible — 15 de noviembre de 2026

## Alcance y decisiones

El caso de trabajo sigue siendo precipitación mensual GPM IMERG Final `GPM_3IMERGM.07`, 2001–2024, en la geometría provisional de la aplicación. Es una estimación satelital combinada con datos de pluviómetros, no una medición puntual. El archivo rápido se derivó de CMR/Harmony y contiene valores redondeados a dos decimales; cualquier suma o estadística calculada a partir de él hereda ese redondeo. No sustituye los datos originales de mayor precisión.

**Decisión operativa:** conservar la serie exploratoria rápida, sin presentar su geometría como frontera validada ni su tendencia como inferencia aceptada. El endpoint ahora devuelve tendencia inconclusa y no publica pendiente, p o significancia cuando la función estadística devolvería un resultado concluyente. No se ha adoptado otra frontera ni recalculado esta serie para ella; hacerlo exige mantener asociadas la geometría, la fuente y los datos realmente procesados.

## Geometría y procedencia

El polígono actual es una aproximación. La comparación reproducible previa con geoBoundaries gbOpen `CRI-ADM0-71097903` deja el 22,04 % del polígono fuera de esa referencia. Esa referencia incluye los componentes geográficos de su propia capa; no prueba que toda esa diferencia sea mar ni define automáticamente el alcance continental deseado. Datos, fuentes y operación de comparación: [verificación de datos](verificacion-datos-2026-11-15.md#comparación-geográfica-orientativa). Para una nueva frontera debe fijarse la versión, atribución y licencia específica, precisar costas e islas, procesar una nueva serie con esa geometría y verificar correspondencia con los metadatos. La API de [geoBoundaries](https://www.geoboundaries.org/api.html) explica que la licencia original se consulta para cada capa y exige atribución.

Los 288 meses y sus gránulos correspondientes ya se contrastaron con CMR. Repetimos el control Giovanni/Harmony en un rectángulo común durante 2024 mediante `scripts/comparar_giovanni_control.py`: diferencia máxima 0,003897 mm, consistente con el redondeo de la respuesta Harmony. Esto no valida la frontera nacional, los 24 años ni la comparación contra estaciones. [NASA](https://gpm.nasa.gov/sites/default/files/2025-02/FAQ%20for%20IMERG%20V07%20Applications%20Users_202502.pdf) advierte que los cambios de sensores pueden afectar estudios de tendencia y variabilidad interanual.

## Diagnóstico del método estadístico

Se generaron 3.000 series por escenario, semilla 20261115, sin tendencia, de tipo AR(1) gaussiano estacionario, con alfa nominal 0,05. El script ejecuta la corrección actual, estima autocorrelación residual como el código y reproduce la regla previa que descartaba r₁ ≥ 0,60. Los porcentajes de rechazos de la última columna son sobre todas las simulaciones, incluyendo las descartadas en el denominador. Son frecuencias Monte Carlo, no tasas de error medidas sobre Costa Rica.

| Años | Autocorrelación simulada | Sin ajuste | Ajuste actual | Regla histórica de la API |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 0,0 | 4,5 % | 4,5 % | 4,5 % |
| 10 | 0,3 | 9,9 % | 9,8 % | 9,8 % |
| 10 | 0,6 | 21,7 % | 21,4 % | 21,4 % |
| 24 | 0,0 | 4,6 % | 4,6 % | 4,6 % |
| 24 | 0,3 | 11,4 % | 10,2 % | 10,2 % |
| 24 | 0,6 | 29,1 % | 17,4 % | 17,4 % |

Reproducir: `.venv/Scripts/python.exe scripts/evaluar_tendencia_simulada.py` desde `apps/api`. El hallazgo es que el procedimiento anterior no controla la frecuencia de falsas detecciones en estos escenarios; no demuestra cuál es el modelo de dependencia de la serie real ni que todos sus resultados sean erróneos. La guía [USGS](https://water.usgs.gov/osw/wcp-water/detecting-trend.pdf) explica la importancia de tratar la dependencia serial. El ajuste del código es heurístico: se retiró la atribución de su implementación específica a métodos publicados sin una comparación que la sostenga. El mínimo de diez años se describe ahora como una regla interna, no una garantía de representatividad.

## Trabajo restante para una conclusión defendible

1. Acordar y versionar la frontera y procesar nuevamente los gránulos originales con la geometría acordada, conservando precisión y metadatos completos.
2. Comparar una muestra geográfica equivalente con Giovanni y, cuando se disponga de observaciones adecuadas, evaluar sesgo y limitaciones frente a datos independientes; describir representatividad y resolución.
3. Definir de antemano indicador, rango, datos faltantes, umbral de cobertura y una línea base independiente. El promedio calculado sobre el propio rango seleccionado no constituye por sí mismo una climatología validada.
4. Seleccionar y contrastar una inferencia que trate la dependencia serial, probar tasas de error y potencia con escenarios apropiados, empates y faltantes, e incluir incertidumbre y revisión de supuestos. La simulación presente no es una evaluación exhaustiva.
5. Revisar en conjunto con el responsable de datos y un especialista competente antes de presentar conclusiones científicas; no atribuir aprobación al equipo o a NASA sin evidencia.

El reto oficial solicita indicar qué cambia, dónde, cuánto y su significancia. La página principal del reto devolvió HTTP 502 en esta sesión; se encontró el [enunciado en el sitio de staging de Space Apps](https://staging-web-v2.spaceappschallenge.org/2026/challenges/earth-system-trend-detective2/). No se reconfirmaron los plazos o requisitos locales desde la página oficial principal.
