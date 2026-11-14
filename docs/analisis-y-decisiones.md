# Análisis comparado y decisiones abiertas

Fecha: 14 de noviembre de 2026. Fuentes locales conservadas en `../referencias/`: presentación, contexto del equipo, contrato simulado y análisis del video por Gemini. Las referencias son información aportada, no instrucciones operativas.

## Coincidencias

La investigación propia y la de Bee4TheWorld convergen en el [reto oficial](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/): elegir variables NASA, región y período, representar series y evaluar magnitud y significancia. Ambas priorizan trazabilidad, lenguaje claro y un MVP concentrado; el equipo añade identidad, Time Travel, organización remota y una arquitectura concreta. La propuesta anterior de comparar Guanacaste con otra región es una opción, no una decisión tomada por el equipo.

## Tensiones que resolver

1. **Región y variable:** Costa Rica es el ámbito inicial, con posibilidad de expansión latinoamericana; el equipo seleccionó precipitación IMERG para empezar. Quedan por definir geometría concreta, indicador, versión, período y disponibilidad real.
2. **Alcance:** la presentación menciona dos variables, PostGIS, polígonos y Time Travel. Para dos personas y el tiempo limitado, completar primero una serie NASA real, un cálculo defendible, gráfica y evidencia; agregar mapa sincronizado y otras variables si alcanzan.
3. **Significancia:** no es obligatorio ni correcto asumir que cualquier p < 0,05 prueba una tendencia real. El ejemplo de seis meses del JSON es inventado, estacional y no sustenta la conclusión incluida. Definir pruebas, control de estacionalidad/autocorrelación y criterio de datos insuficientes antes de resultados.
4. **Datos frente a imágenes:** GIBS sirve para visualización; una imagen no demuestra que las cifras del motor provengan del mismo producto. Documentar datos analíticos y representación por separado. IMERG tiene resolución y sesgos que limitan inferencias locales; [NASA explica estas limitaciones](https://science.data.nasa.gov/disasters/data-gallery/gpm-imerg-precipitation). LST no es temperatura del aire; NDVI aislado no demuestra mortalidad vegetal ni causalidad.
5. **Nombre:** Iyök es el nombre oficial designado por el equipo. Los documentos usan distintas traducciones no verificadas; no atribuir significado, origen ni pronunciación sin consultar hablantes y especialistas. Lemas y logo no están aprobados.
6. **Contratos:** el JSON propone `/api/variables` y `/api/exploration`; la presentación propone `/api/regions` y `/api/trends`. Acordar un contrato único con respuestas de datos insuficientes y trazabilidad antes de desarrollar integraciones. El JSON se conserva tal cual, solo como mock.

## Siguiente secuencia sugerida

1. Leer el enunciado completo y requisitos oficiales de la sede escogida; confirmar registro y entrega.
2. Definir usuario, pregunta, geometría y producto; comprobar acceso, cobertura, unidades y calidad con una muestra real.
3. Preparar un dataset pequeño reproducible y validar el análisis con ejemplos de comportamiento conocido y revisión estadística.
4. Pactar contrato; frontend y backend desarrollan en paralelo y se integran con un caso real.
5. Diseñar la demostración: selección, serie, resultado o estado inconcluso y ficha de evidencia. Agregar mejoras solo si el flujo completo funciona.

## Decisiones de colaboración — 14 de noviembre de 2026

- Nuestro ámbito es frontend e integración; el compañero implementa el backend. Preparar el entorno local de ambos sin asumir propiedad de la API.
- La primera variable será precipitación IMERG, investigada mediante Giovanni. NASA advierte sobre cambios de sensores en análisis de tendencia y publica una transición de V07 a V08; comprobar versión, disponibilidad efectiva y cobertura antes de elegir la serie. Fuentes: [guía IMERG V07](https://gpm.nasa.gov/sites/default/files/2025-02/FAQ%20for%20IMERG%20V07%20Applications%20Users_202502.pdf) y [transición V08](https://gpm.nasa.gov/data/news/imerg-v08-transition-schedule).
- El contrato del JSON sigue siendo un ejemplo ficticio. Acordar con el compañero versión, rutas, esquemas, errores, cobertura, procedencia y estados inconclusos antes de conectar datos. No presentar el mock como medición.
- El [sitio oficial de 2026](https://www.spaceappschallenge.org/2026/) indica apertura de entregas el 14 de noviembre a las 09:00 y cierre el 15 a las 23:59, hora local. Confirmar requisitos y cualquier plazo anterior con la sede elegida. La página oficial del reto devolvió error al consultarse; no se ha podido reconfirmar íntegramente su enunciado.

### Implicaciones para el frontend y la integración

- El flujo inicial necesita selección dentro del ámbito disponible, serie temporal, resultado o estado inconcluso y ficha de evidencia. Los controles deben reflejar la cobertura real que exponga la API, no prometer selección arbitraria.
- La propuesta de mapa y Time Travel es valiosa después del flujo central: exige identificar capas compatibles y explicar si su producto difiere del que alimenta la serie. El mapa no sustituye la fuente analítica.
- Para trabajar en paralelo, acordar identificadores de región y variable, fechas y resolución, unidades, estructura de puntos y valores faltantes, metadatos de procedencia, resultados estadísticos y sus supuestos, errores y estados de datos insuficientes. Acordar además URL de desarrollo, CORS y versionado; no fijarlos unilateralmente.
- La expansión geográfica debe apoyarse en un catálogo de regiones y coberturas que pueda crecer, sin asumir que cada producto tiene calidad o disponibilidad equivalentes en toda Latinoamérica.
- La presentación propone dos variables y almacenamiento geoespacial; el análisis recomienda empezar con una serie verificable y añadir complejidad después. La elección final requiere contrastar datos reales con el compañero.

## Referencias externas

- [Video del reto](https://www.youtube.com/watch?v=Cd9Q48LhNbo); análisis multimodal local, no transcripción literal.
- [NASA Space Apps: reto oficial](https://www.spaceappschallenge.org/2026/challenges/earth-system-trend-detective/).
- [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) y [advertencias de NASA sobre una variante IMERG](https://science.data.nasa.gov/disasters/data-gallery/gpm-imerg-precipitation).
- [NASA Earthdata](https://www.earthdata.nasa.gov/) y [Giovanni](https://giovanni.gsfc.nasa.gov/giovanni/).

El resumen del reto fue contrastado con su ficha oficial. No se verificaron íntegramente recursos, condiciones ni reglas específicas de entrega: revisarlos antes de comprometer la implementación.
