# Issue #11: investigación para el mapa temporal

Fecha: 15 de noviembre de 2026. Estado: investigación inicial. La implementación y su verificación se describen en el [traspaso del mapa](traspaso-mapa-issue-11.md).

## Punto de partida

El issue pide un mapa y un control temporal sincronizados cuando existan capas compatibles, con fechas y fuentes identificadas y diferencias respecto de los datos analíticos explicadas. El frontend ya consulta una serie mensual regional y utiliza ECharts; cada punto es un promedio territorial, no un campo espacial. No se puede reconstruir la distribución de lluvia por celda a partir de esos promedios.

La geometría utilizada por la serie es el componente terrestre principal de la unión provincial IGN/SNIT, identificado por SHA-256 `ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb`. Se excluyen los componentes separados; la revisión científica sigue pendiente. La fuente, atribución y límites se detallan en [frontera SNIT](frontera-snit-analisis-2026-11-15.md). Los 288 recortes mensuales de IMERG Final V07 existen en la caché local ignorada por Git y cuentan con un respaldo privado; cubren el rectángulo descargado, no el planeta. Véase [respaldo](respaldo-recortes-supabase.md). La existencia de archivos no constituye validación científica ni autoriza su publicación sin revisar las condiciones de distribución.

Los ejemplos solicitados en `docs/assets` no aparecen en este checkout; queda pendiente conocer su ubicación y examinarlos antes de fijar la dirección visual.

## Opciones técnicas

| Opción | Encaje y límites |
| --- | --- |
| [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/) | Recomendación inicial: mapa interactivo, capas GeoJSON y ráster, navegación y ejemplos de animación. Ya está previsto en `DEPENDENCIAS.md`, pero aún no está instalado. Requiere comprobar WebGL y ofrecer un estado alternativo cuando no esté disponible. |
| [OpenLayers](https://openlayers.org/) | Alternativa a evaluar si el acceso directo a formatos geoespaciales, proyecciones o servicios cartográficos resulta decisivo. Introducirlo en vez de MapLibre requiere justificar la complejidad adicional para este MVP. |
| [ECharts](https://echarts.apache.org/) | Ya se usa para la serie; puede seguir mostrando la gráfica y compartir con el mapa un mes seleccionado. No es necesario sustituir la gráfica para implementar el mapa. |
| Impeccable | Skill local de diseño de interfaz; ayuda a conservar el lenguaje visual y verificar accesibilidad y tamaños de pantalla. No aporta datos ni un motor cartográfico. |

[MapLibre documenta](https://maplibre.org/maplibre-gl-js/docs/examples/) fuentes GeoJSON y ráster, WMS y animación de imágenes. Su [fuente de imagen](https://maplibre.org/maplibre-gl-js/docs/API/classes/ImageSource/) permite cambiar una imagen georreferenciada para cada mes. La elección de biblioteca no resuelve por sí misma la generación de datos, escala de colores, licencias o sincronización.

## Ruta propuesta

1. Revisar los ejemplos visuales solicitados y definir una interacción accesible de navegación, selección de mes y leyenda, adaptada a escritorio y móvil.
2. Inspeccionar los recortes y el proceso existente. Preparar, como derivado reproducible, una capa por mes a partir de los mismos datos y variable usados por la serie, con conversión de unidades explícita, celdas ausentes, resolución y límites geográficos documentados. Conservar un manifiesto con fechas, producto, gránulos, huellas y método. Comparar los datos de varias celdas y el cálculo regional contra los originales; una imagen coloreada no sustituye los valores analíticos.
3. Mostrar la frontera correspondiente y explicar que la capa representa estimaciones por celda, mientras la gráfica representa un promedio ponderado del territorio. No mostrar la precipitación del rectángulo como si toda perteneciera a Costa Rica. Verificar condiciones de redistribución y atribución de NASA y de IGN/SNIT antes de servir derivados públicamente; si se simplifica la geometría visual, documentar que no es la usada para calcular.
4. Usar un mes seleccionado compartido entre mapa y gráfica dentro del intervalo consultado. Cambiar el período o iniciar una nueva consulta debe retirar los datos anteriores; manejar meses ausentes, carga y errores sin mostrar capas desfasadas. El control debe funcionar con teclado y acompañarse de fecha, unidades, leyenda, fuente y tabla accesible.
5. Probar integridad y correspondencia temporal y espacial con datos conocidos, estados de error, interacción, rendimiento y visualización en escritorio y móvil. Mantener visible que la serie y el método siguen en revisión científica.

Un fondo cartográfico es una fuente independiente: elegir proveedor tras revisar disponibilidad, atribución, límites y uso sin conexión. Por ejemplo, la [política del servidor de teselas de OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/) exige atribución visible y restringe la descarga masiva; el servicio no ofrece garantía de disponibilidad. Las imágenes de contexto NASA GIBS o productos IMERG Early no deben presentarse como la capa mensual Final usada en el análisis sin comprobar producto, versión, fechas y método.

## Pendientes antes de cerrar el issue

- Ubicar las referencias visuales de `docs/assets`.
- Verificar variable, coordenadas, conversión, máscara y rango para las capas derivadas; definir leyenda y tratamiento de valores ausentes.
- Comprobar condiciones de publicación y el proveedor del mapa base; conservar la atribución.
- Revisar la relación entre geometría, píxeles y promedio con Gabriel y documentar los límites científicos.
- Implementar y verificar el mapa y su sincronización; esta investigación no acredita esos criterios de aceptación.
