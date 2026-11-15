# Propuesta de integración frontend–backend

**Estado: borrador histórico 0.1.** La implementación posterior y su alcance operativo se describen en [contrato API v1](contrato-api-v1.md); este documento conserva la propuesta anterior y no refleja necesariamente el estado actual. El compañero lidera la ingesta, el análisis y el backend. `referencias/iyok_api_contracts_mock.json` es un ejemplo ficticio anterior y no valida resultados científicos.

## Objetivo y límites

Permitir que el frontend presente una serie verificable de precipitación IMERG para un área de Costa Rica, junto con el análisis disponible o una explicación de por qué es inconcluso. La geometría, indicador, versión del producto, período y método requieren validación conjunta. El diseño debe admitir más regiones latinoamericanas sin presumir que tengan la misma cobertura o calidad.

El frontend presenta los resultados y su evidencia; no calcula significancia ni inventa valores o metadatos. El backend determina cobertura, calidad y validez del análisis. El ejemplo actual de la interfaz es ficticio y permanece separado de cualquier fuente científica.

## Operaciones candidatas

| Necesidad | Propuesta para revisión | Resultado esperado |
| --- | --- | --- |
| Opciones disponibles | `GET /api/v1/catalog` | Regiones y variables con identificadores estables, etiquetas y combinaciones disponibles. |
| Cobertura | Incluida en cada combinación del catálogo | Intervalos realmente disponibles, resolución temporal y restricciones; no asumir que la cobertura de cada región coincide. |
| Explorar | `POST /api/v1/explorations` | Serie y análisis correspondientes exactamente a la selección, con procedencia y advertencias. |

Se propone `v1` para un contrato acordado; **no existe aún**. El equipo puede preferir rutas separadas o archivos estáticos. La versión del documento (0.1) no es la versión de una API publicada.

### Catálogo y cobertura

Para cada combinación disponible: identificadores estables de región y variable, nombres legibles, producto e indicador, unidad, resolución temporal, inicio y fin inclusivos de cobertura y restricciones relevantes. Si hay huecos de cobertura, describir intervalos disponibles en vez de prometer continuidad. La región debe tener una referencia a su geometría, versión y fuente; un nombre como «Costa Rica» no basta para reproducir la agregación. Un catálogo vacío debe distinguirse de un error de servicio.

### Solicitud de exploración

Propuesta de campos: `region_id`, `variable_id`, `start_date`, `end_date` y resolución temporal elegida entre las opciones del catálogo. Usar fechas ISO 8601, indicar límites inclusivos y si los puntos representan intervalos o instantes; precisar calendario, zona horaria cuando aplique y alineación de períodos mensuales antes de implementar. La API debe rechazar identificadores desconocidos, rangos invertidos, combinaciones o fechas fuera de cobertura y resoluciones incompatibles; no recortar silenciosamente la solicitud.

### Respuesta de exploración

- **Selección efectiva:** región y referencia de geometría, indicador/producto, período solicitado y utilizado, resolución y unidad. Si el período efectivo difiere, explicar por qué; no atribuir el resultado a otra selección.
- **Serie:** puntos ordenados con fecha o límites de intervalo y valor numérico finito, o `null` cuando falte. No usar cero para datos ausentes; informar causa conocida, cobertura y criterios de agregación. Fechas, unidad y significado del valor deben ser inequívocos.
- **Análisis:** estado `conclusive`, `inconclusive` o `not_computed` propuesto. Una serie válida puede acompañar un resultado inconcluso. Para un resultado válido incluir dirección, pendiente y sus unidades y escala temporal, método, período, supuestos y tratamiento de estacionalidad, autocorrelación y faltantes. Añadir intervalo de confianza, valor p y umbral solo cuando correspondan, junto con su método; no inferir causalidad ni importancia práctica. Para resultado inconcluso o no calculado incluir motivo comprensible y no fabricar estadísticas.
- **Procedencia:** proveedor, nombre e identificador del producto y versión, enlace o DOI, fecha de acceso, origen satelital o de modelo, resolución espacial y temporal, unidad, filtros de calidad, cobertura, agregación espacial y temporal, tratamiento de faltantes, fuente y versión de geometría, licencia o condiciones y limitaciones. Incluir identificador o versión del conjunto procesado y código o método reproducible cuando existan.
- **Advertencias:** texto que explique limitaciones científicas y de cobertura. IMERG no sustituye mediciones puntuales de estaciones; la resolución y los sesgos en zonas montañosas y costeras deben revisarse para el producto y área elegidos.

Campos todavía desconocidos deben representarse explícitamente como pendientes o ausentes, con su motivo cuando sea posible; no inventar valores para satisfacer una estructura. Antes de aceptar resultados reales acordar cuáles metadatos son obligatorios y cuándo impedir su presentación como resultado verificable.

## Estados y errores propuestos

| Situación | Propuesta | Comportamiento del frontend |
| --- | --- | --- |
| Solicitud inválida | `400` o `422`, código estable y mensaje seguro | Explicar el campo o rango que debe corregirse. |
| Identificador inexistente | `404`, código estable | Informar que la opción no está disponible y actualizar el catálogo si procede. |
| Selección sin cobertura | Código y estado HTTP por acordar | Explicar la falta de datos sin representar ceros; ofrecer opciones disponibles si se conocen. |
| Datos válidos, análisis inconcluso | Respuesta exitosa con serie y estado explícito | Mostrar la serie y la razón, sin conclusión estadística. |
| Error del servicio o fuente | `5xx` o error de red | Informar el fallo y permitir reintento; no exponer detalles internos. |

Propuesta de sobre de error: `code` estable para el cliente, `message` seguro para personas y `details` opcional con campos afectados; definir idioma, códigos y HTTP exactos con el compañero. No enviar credenciales, rutas internas ni trazas en errores. El estado de carga lo controla el frontend y no constituye un resultado científico.

## Integración y seguridad

- Acordar URL de desarrollo, orígenes CORS, autenticación, límites de tiempo y política de reintento. No incorporar tokens Earthdata al navegador, a ejemplos ni al repositorio; la ingesta autenticada corresponde al entorno seguro del backend.
- Validar respuestas externas en ejecución antes de presentarlas, además de utilizar tipos estáticos; rechazar esquemas incompatibles, unidades ausentes y números no finitos. Definir compatibilidad de cambios y estrategia de versionado en conjunto.
- El puerto `DemonstrationSource` actual solo encapsula el ejemplo ficticio. No es el contrato real ni acepta aún selección, cobertura o procedencia. Tras acordar esquemas, crear un puerto de exploración real y un adaptador HTTP o de archivo validado; mantener las fuentes real y ficticia claramente separadas.
- Para una demo sin red, acordar un conjunto preprocesado versionado con la misma trazabilidad y la misma semántica del contrato. No presentar una capa visual de mapa como la medición analítica salvo que se verifique su correspondencia.

## Acuerdos pendientes para revisión conjunta

1. Geometría y fuente, indicador IMERG, versión de producto, unidades, período y resolución disponibles; muestra real y evidencia de acceso.
2. Rutas, esquemas exactos, versión, fechas inclusivas, cobertura discontinua y representación de faltantes.
3. Método estadístico, supuestos, umbral, incertidumbre, tratamiento de estacionalidad/autocorrelación y criterios de resultado inconcluso.
4. Metadatos obligatorios, licencia, reproducibilidad y límites mínimos para mostrar un resultado como verificable.
5. Errores y códigos HTTP, configuración local, CORS, autenticación y estrategia de datos preprocesados.
6. Pruebas de contrato con casos reales y sintéticos identificados: éxito, faltantes, fuera de cobertura, inconcluso, error y respuesta incompatible.

**Criterio para cerrar el issue:** ambos integrantes revisan y acuerdan el contrato, se registra la versión acordada y existe una capa cliente desacoplada y validada contra el acuerdo. Este borrador y el puerto de demostración por sí solos no cumplen ese criterio.
