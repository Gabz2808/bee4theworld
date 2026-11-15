# Evaluación de la frontera IGN/SNIT para Iyök

Fecha de consulta: 15 de noviembre de 2026. La revisión del repositorio privado [Pura Vida Trueque](https://github.com/alquimiacria/pura-vida-trueque) se hizo con autorización del propietario, sobre el commit `8d71c9eb4a10c0e77a3a049f1f477c3687609c43`.

## Qué hace Pura Vida Trueque

Su [script geográfico](https://github.com/alquimiacria/pura-vida-trueque/blob/8d71c9eb4a10c0e77a3a049f1f477c3687609c43/scripts/geo/build_costa_rica_districts.py) descarga la capa distrital `IGN_5_CO:limitedistrital_5k`, transforma cada distrito en un punto representativo interior y guarda coordenadas y códigos para un catálogo de ubicación. El [catálogo generado](https://github.com/alquimiacria/pura-vida-trueque/blob/8d71c9eb4a10c0e77a3a049f1f477c3687609c43/firebase_bootstrap/data/costa_rica_districts.json) documenta 7 provincias, 84 cantones y 494 distritos; conserva puntos, no los polígonos originales. Esos puntos no permiten reconstruir una frontera ni calcular promedios de precipitación por área.

El [registro de metadatos IGN/SNIT](https://meta2.snitcr.go.cr/geonetwork/srv/api/records/CR_IGN_LTA_DTA_5K_VE) fue consultado directamente: describe la división territorial administrativa oficial a escala 1:5.000, declara actualización del 10 de abril de 2026 y enlaza las capas distrital y provincial. Indica uso libre y gratuito con mención del origen y propiedad de los datos; conservar la atribución IGN/Registro Nacional/SNIT y revisar sus condiciones antes de distribuir derivados. No se comprobó una licencia estandarizada adicional.

## Comparación reproducible

Se consultó directamente [WFS IGN/SNIT](https://geos.snitcr.go.cr/be/IGN_5_CO/wfs?service=WFS&version=2.0.0&request=GetCapabilities), capa `IGN_5_CO:limiteprovincial_5k`, pidiendo GeoJSON EPSG:4326. Se recibieron siete geometrías provinciales válidas; su unión es un `MultiPolygon` válido con 121 componentes y 563.977 vértices. La respuesta ocupa aproximadamente 19,8 MB. Se calcularon áreas e intersecciones en EPSG:6933, como en el análisis previo:

| Medida | Resultado |
| --- | ---: |
| Unión provincial SNIT | 51.174,75 km² |
| Polígono provisional Iyök | 63.008,76 km² |
| Intersección | 49.203,52 km² |
| Parte del polígono provisional fuera de SNIT | 21,910 % |
| Parte de SNIT fuera del polígono provisional | 3,852 % |
| Componente de mayor área | 51.092,24 km² |
| Área de los otros 120 componentes | 82,51 km² |

La extensión de la capa llega aproximadamente a 5,499° N y 87,102° O; contiene componentes alejados del territorio continental. La geometría mayor no se ha clasificado automáticamente como una definición completa y correcta de «continental»: se deben examinar sus componentes, costas e islas y acordar el ámbito. Los porcentajes describen estas geometrías, no identifican automáticamente qué parte es mar o pertenece a otros países.

Ejecutar desde `apps/api`: `.venv/Scripts/python.exe scripts/comparar_frontera_snit.py`. El servicio es dinámico y no se archivó el archivo de 19,8 MB; la huella SHA-256 de una respuesta fue `ca260b62f458b776c1b55490d47e8d519afb525c2f93bfcfda47fc8bebf26295`. Otra descarga tuvo una huella diferente pese a producir las mismas métricas redondeadas; no se comprobó equivalencia exacta entre respuestas. Es necesario archivar y verificar una instantánea identificada antes de afirmar reproducibilidad exacta.

### Captura posterior para el issue #22

Se archivó una **nueva respuesta** del WFS en [`datos/fuentes/snit-provincial-2026-11-15/`](../datos/fuentes/snit-provincial-2026-11-15/), con atribución, parámetros, fecha de acceso y huellas en `metadatos.json`. Su GeoJSON descomprimido tiene SHA-256 `c948df270d724e1d0c602c0a38942a0fce2ea5076b8631cb05480138ef19cf59`; el archivo comprimido ocupa 5.947.425 bytes. Esta es una captura distinta de la usada en la tabla anterior: no se ha demostrado que ambas geometrías sean idénticas. No se ha seleccionado aún una geometría final ni evaluado la redistribución específica con el equipo.

Desde `apps/api`, `.venv/Scripts/python.exe scripts/capturar_frontera_snit.py verify` comprueba huellas, CRS, siete nombres de provincias, geometrías válidas y una extensión geográfica básica sin acceso a la red. `.venv/Scripts/python.exe scripts/comparar_frontera_snit.py --snapshot` usa esa captura para recalcular las áreas; se ejecutó y reprodujo los valores de la tabla al redondeo mostrado. Esto no demuestra igualdad geométrica exacta con la respuesta previa. El comando `capture` descarga una fuente nueva y se niega a sobrescribir la captura existente. Estas comprobaciones establecen integridad y coherencia básica, no validan exactitud cartográfica ni el ámbito continental.

## Decisión propuesta y adaptación

### Decisión para el MVP y avance del 15 de noviembre

Manuel indicó priorizar el territorio continental y dejar las islas para una versión posterior. Se seleccionó de forma operativa el componente de mayor área de la unión provincial, sin simplificar, como un `MultiPolygon` de un componente. Esto excluye los 120 componentes separados (82,51 km² según EPSG:6933); no se clasificó cada componente individualmente. La geometría derivada está en `datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz`; la huella SHA-256 del GeoJSON descomprimido es `ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb`. La instantánea fuente y su atribución están en el mismo directorio.

El conector espacial admite polígonos y multipolígonos, incluidas partes separadas y huecos; la API limita en conjunto los vértices y la extensión de las geometrías enviadas por usuarios. Una prueba con la frontera completa y una cuadrícula sintética de 0,1° cubrió el área geométrica calculada; no valida por sí sola datos NASA. `scripts/generar_serie_snit.py` descarga CMR/Harmony 2001–2024 con la nueva geometría, conserva valores sin el redondeo de presentación e incluye fuente, gránulos y huellas. `scripts/verificar_serie_snit.py` comprueba la salida y compara con la serie anterior. La web y el catálogo no se han cambiado: la serie anterior aún corresponde al polígono provisional y no debe presentarse como si usara SNIT.

La extracción es un trabajo remoto y puede tardar más que el timeout de la web. No existe todavía un flujo de trabajos con estado para usuarios: comprobar su finalización y los 288 meses antes de incorporar la salida al producto. La cobertura espacial calculada tampoco constituye una validación de la calidad científica de IMERG.

El trabajo Harmony para 2001–2024 iniciado en esta sesión tiene identificador `054695e5-f58a-47f6-a365-bf600d9d0b6d` y terminó remotamente. Se conservaron 288 recortes NetCDF en `apps/api/data/cache/imerg-snit-2001-2024-harmony-054695e5/` (carpeta local ignorada por Git), con un manifiesto de huellas, dimensiones temporales y cobertura; ocupan unos 22 MB. Los recortes cubren únicamente el rectángulo solicitado, no son gránulos globales completos. Se verificó que cada uno se abre y tiene un mes distinto, secuencial, y la variable declara `mm/hr`.

Como el procesamiento local original continuaba consumiendo CPU tras la descarga, se detuvo ese proceso redundante después de guardar y comprobar la caché. Se procesaron los recortes con `scripts/procesar_cache_snit.py`, leyendo solo la variable de precipitación y usando la misma función de ponderación espacial de la API. La salida es `datos/procesados/imerg-snit-continental-2001-2024-cache-v1.json`. `scripts/verificar_serie_snit.py ../../datos/procesados/imerg-snit-continental-2001-2024-cache-v1.json` comprobó 288 meses consecutivos, 288 identificadores únicos y huella de geometría; la cobertura espacial mínima calculada fue 0,9999979. Enero de 2024 coincide exactamente con el control independiente en valor y cobertura. Frente a la serie provisional redondeada, la diferencia absoluta mediana fue 10,8 mm/mes y la máxima 59,06 mm/mes. Estas diferencias no son una validación de la serie ni demuestran tendencia.

Como control independiente se extrajo enero de 2024 para la nueva geometría con `scripts/control_snit_enero_2024.py`: el archivo `datos/procesados/imerg-snit-control-2024-01.json` conserva la huella geométrica, unidades, fecha, método y gránulo. El resultado es aproximadamente 70,38 mm/mes, frente a 66,03 mm/mes en la respuesta redondeada con el polígono anterior; ambos identifican el gránulo `G3087531387-GES_DISC`. La cobertura espacial calculada para la nueva geometría fue 0,9999979 y la regla actual la marca como parcial; debe investigarse la pequeña diferencia antes de interpretarla como problema de datos o como error numérico. La comparación muestra sensibilidad al ámbito, no valida la serie completa ni demuestra una tendencia.

La consulta directa a CMR identificó la colección `C2723754851-GES_DISC` como GPM IMERG Final mensual 0,1° V07, con DOI [10.5067/GPM/IMERG/3B-MONTH/07](https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07). La serie se deriva de estimaciones satelitales combinadas, no de mediciones puntuales en estaciones.

**SNIT es una candidata fuerte** para definir el territorio: proporciona polígonos de una fuente nacional identificable y una condición de uso expresada en sus metadatos. La revisión no valida por sí sola su exactitud para la pregunta de precipitación ni determina la selección continental definitiva. Debe acordarse el tratamiento de las islas, verificar la licencia para la distribución específica y fijar una instantánea, fecha y huella.

La integración actual exige cambios: el catálogo, los modelos y el cliente esperan `Polygon`, y el conector construye `shapely.geometry.Polygon`; la solicitud de geometrías está limitada a 500 vértices y 1 MB. La unión oficial es `MultiPolygon` y tiene más vértices. No hay que eliminar islas o simplificar sin medir el efecto sobre la superficie y sobre la ponderación de las celdas IMERG. Una frontera interna versionada podría evitar enviar un archivo completo por solicitud, manteniendo los límites de seguridad para geometrías aportadas por usuarios.

Después de elegir el ámbito se requiere **reprocesar** los gránulos NASA con esa geometría y asociar la serie nueva a su huella, fuente, método y fecha de acceso; la serie rápida actual pertenece al polígono provisional. Comparar la serie nueva con la anterior y registrar las diferencias, sin tratarlas como errores por defecto. La validación estadística y de datos sigue siendo un trabajo separado de la selección de frontera.
