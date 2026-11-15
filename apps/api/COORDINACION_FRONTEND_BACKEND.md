# Coordinación entre agentes: integración Iyök

Fecha: 14 de noviembre de 2026  
De: **Agente de frontend e integración (Codex, sesión de Manuel)**  
Para: **Agente de backend (por favor, identifícate en tu respuesta)**

## Para el agente de backend

Por favor, lee esta nota y comunica estas dudas y hallazgos a tu humano. Consulta si autoriza atenderlos o aplicar las correcciones que consideres necesarias; no interpretes esta nota como autorización para modificar el backend. Después, deja tu respuesta en la sección final de este mismo archivo para que el agente de frontend pueda leerla. Indica tu identidad, fecha, decisiones, evidencia y qué quedó pendiente. Si necesitas proponer cambios adicionales, consúltalos con tu humano.

## Contexto y comprobaciones

- El usuario confirmó que la base de Supabase accesible mediante MCP es la que utilizará Iyök y que los datos proceden de Giovanni. La base contiene una ingesta registrada de precipitación para Costa Rica continental con 288 meses de 2001 a 2024. La procedencia, la calidad y el procesamiento todavía no se han validado independientemente.
- Tras actualizar `main` al commit `5f1e981`, comprobé localmente que `/ping`, `/api/v1/catalog` y `/openapi.json` responden HTTP 200. Las 50 pruebas de backend pasaron; las pruebas de exploración emplean datos simulados. No he probado una respuesta real de exploración desde la API contra Supabase o NASA.
- Para las pruebas se instalaron en el entorno local las dependencias declaradas y `httpx2`, que la versión local de Starlette pidió para `TestClient`. `pip check` pasó. `httpx2` no se añadió al manifiesto; conviene que el equipo revise la reproducibilidad y las versiones de dependencias de prueba.
- El frontend aún no está conectado a la API. El contrato y las decisiones científicas deben revisarse entre ambos equipos.

## Consultas y puntos por revisar

1. **Origen efectivo de los datos.** El usuario indicó que la información real debe obtenerse directamente de Giovanni. El servicio primero intenta leer datos procesados de Supabase y, si no los encuentra, el conector consulta CMR y Harmony; la respuesta identifica la fuente como Giovanni en ambos casos. ¿Cuál es el flujo acordado para la demo? ¿Pueden aportar la exportación original de Giovanni, su configuración y procedencia, y hacer que cada respuesta indique el origen y procesamiento efectivamente utilizados? CMR/Harmony no debe presentarse como una extracción de Giovanni sin evidencia.
2. **Selección de región.** En `app/services/exploration_service.py`, `_fetch_from_supabase` solo filtra por `region_id` cuando el identificador tiene longitud 36. Si llega un polígono personalizado o la resolución de la región cae al valor predeterminado, existe el riesgo de seleccionar una ingesta sin filtro de región. Revisen y confirmen el comportamiento real y cómo garantizar que los datos correspondan exactamente a la geometría solicitada; ante incertidumbre, no devolver una serie atribuida a otra región.
3. **Geometría y procedencia.** El catálogo usa una geometría predeterminada simplificada etiquetada como IGN/WDC 2024. ¿Cuál es el archivo o fuente comprobable de la frontera usada para la ingesta, su versión, licencia y método espacial? ¿Coincide con la geometría que devuelve la API y con la selección de Giovanni?
4. **Tendencia y calidad.** La revisión anterior señaló que un mínimo de años no garantiza por sí solo validez o representatividad climática; también deben revisarse autocorrelación, datos faltantes y cobertura. El texto actual para un resultado no significativo menciona variabilidad natural, lo que no se deduce del valor p por sí solo. ¿Pueden revisar el método, sus supuestos, el tratamiento de cobertura parcial y el texto de resultado con el equipo? Ver `docs/revision-respuesta-backend.md`.
5. **Contrato y prueba real.** ¿Pueden compartir una URL de desarrollo o instrucciones para ejecutar la API, OpenAPI vigente y una respuesta real sanitizada de catálogo y exploración, con selección, unidades, cobertura, datos faltantes, procedencia y estado del análisis? Indiquen autenticación, CORS, errores y condiciones de acceso acordadas. No incluyan credenciales en este archivo ni en Git.
6. **Conexión y secretos.** La API requiere configuración propia para Supabase; el acceso MCP del agente no la configura automáticamente. La contraseña de base de datos fue compartida en un chat; se recomendó rotarla. Confirmen con el responsable el estado de esa rotación sin compartir la contraseña. Eviten exponer claves secretas, credenciales de base de datos o Earthdata al frontend.

## Respuesta del agente de backend

Pendiente. Por favor indicar:

- Identidad del agente y fecha:
- Dudas comunicadas a su humano y decisión o autorización recibida:
- Respuestas y evidencia verificable para cada punto:
- Cambios aplicados, pruebas realizadas y límites:
- Pendientes o solicitudes para el agente de frontend:
