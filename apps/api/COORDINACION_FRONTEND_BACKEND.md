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

## Avance del agente de frontend — cliente provisional

El agente de frontend e integración agregó `apps/web/src/app/lib/api-v1.ts` y pruebas con datos sintéticos. Define un puerto con cliente HTTP para `GET /api/v1/catalog` y `POST /api/v1/explorations`; recibe URL y transporte por inyección, valida la estructura en tiempo de ejecución y distingue errores HTTP, red y respuesta incompatible. Conserva ceros, valores ausentes, cobertura y calidad; mantiene el resultado como `api_unverified`. No conecta el cliente a la interfaz ni presenta la interpretación estadística como validada. La forma se basa en el código del backend del commit `5f1e981`, no en un contrato aprobado.

Las pruebas cubren catálogo, referencias a región/variable, ceros, faltantes, cobertura parcial, resultado inconcluso, fechas inválidas, selección temporal distinta, unidad ausente, error fuera de cobertura, fallo de red y respuesta incompatible. Son simulaciones. También se validó una respuesta del catálogo servido por la API local, que utiliza datos predeterminados; quedan pendientes una prueba de exploración con respuesta real sanitizada y revisión conjunta del acuerdo.

### Diferencias y preguntas para acordar

- El borrador `docs/propuesta-integracion.md` dice que aún no existe API v1; el código ya implementa las rutas y genera OpenAPI, pero el contrato continúa sin acuerdo. Debe actualizarse cuando ambos integrantes lo aprueben.
- El backend acepta `region_id` o geometría, y dos formatos de fechas; el cliente provisional solo envía `region_id` y `start_date`/`end_date` mensuales. Por favor confirmar el subconjunto aprobado y qué ocurre cuando se reciben formas simultáneas o contradictorias.
- El catálogo anuncia un identificador legible de región, mientras la exploración puede devolver un UUID de base de datos. El cliente verifica los períodos, pero **no puede comprobar por sí solo que la región devuelta corresponda a la solicitada**. Acordar identificadores estables y resolver el riesgo de selección de ingesta descrito arriba antes de usar resultados.
- El catálogo está construido con valores predeterminados y declara disponibilidad; una respuesta 200 no verifica disponibilidad efectiva de la serie. Confirmar cobertura y huecos con la fuente real.
- Los modelos incluyen fuente, producto, unidad, selección y advertencias, pero faltan o no están garantizados en la respuesta identificador de ingesta, fecha de acceso, enlace o DOI, conversión y método/versión efectivos de procesamiento. Acordar campos obligatorios y cómo distinguir Giovanni de Harmony.
- El modelo permite `selection` ausente, mientras el servicio actual la devuelve; el cliente provisional la exige para comprobar fechas. Solicita confirmación de obligatoriedad, rangos inclusivos y comportamiento cuando el período efectivo difiere.
- El error observado contiene `code`, `message` y `details`; el cliente conserva código y estado HTTP, sin exponer texto interno. Acordar códigos de ausencia de cobertura, validación, fallo de fuente y compatibilidad.
- La configuración CORS y el acceso de desarrollo aún no están acordados. Las claves de Supabase y Earthdata no deben llegar al navegador.

## Integración de la interfaz — avance adicional de frontend

La interfaz usa ahora el cliente provisional con catálogo y exploración a través de rutas del servidor Next.js. Muestra la serie como pendiente de validación y no presenta conclusiones estadísticas. El intervalo anunciado por el catálogo se identifica como disponibilidad no confirmada. En local se comprobó catálogo 200 y error de selección 400 a través de Next.js hacia FastAPI; la prueba visual de exploración utilizó una respuesta sintética, no una consulta real de datos. No hay `SUPABASE_URL` ni `SUPABASE_SECRET_KEY` configurados en el proceso de API de este entorno. Sigue siendo necesario verificar con backend región, procedencia y respuesta real antes de utilizar el resultado en la demo.

## Respuesta del agente de backend

Pendiente. Por favor indicar:

- Identidad del agente y fecha:
- Dudas comunicadas a su humano y decisión o autorización recibida:
- Respuestas y evidencia verificable para cada punto:
- Cambios aplicados, pruebas realizadas y límites:
- Pendientes o solicitudes para el agente de frontend:
