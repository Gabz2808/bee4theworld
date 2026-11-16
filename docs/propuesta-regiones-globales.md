# Propuesta: más regiones y países en Iyök

Estado: propuesta para revisar con Gabriel (15 de noviembre de 2026). Queda fuera del MVP. Las licencias de GAUL y GADM se comprobaron solo en fuentes secundarias; confirmarlas en el sitio de cada proveedor antes de usar sus datos.

## Contexto

En el MVP se usa el componente terrestre principal de la unión provincial IGN/SNIT de Costa Rica. Añadir otra región implica repetir todo el proceso: geometría, recorte IMERG, máscara, agregación, revisión científica y procedencia. Cambiar el polígono del mapa no basta.

## Fuentes globales de límites

| Fuente | Niveles | Licencia | Uso propuesto |
|---|---|---|---|
| geoBoundaries (William & Mary geoLab) | ADM0 a ADM5 según el país | CC BY 4.0 | Fuente por defecto. Usar gbOpen, que trae la fuente oficial de cada país en sus metadatos. CGAZ, una versión simplificada, sirve como base del mapa. |
| FAO GAUL 2024 | País, nivel 1 y nivel 2 | CC BY 4.0 (por confirmar) | Alternativa cuando se necesiten códigos uniformes en varios países. |
| Natural Earth | País y nivel 1, a escala 1:10m | Dominio público | Solo como fondo cartográfico. Es demasiado gruesa para calcular sobre ella. |
| GADM | Hasta 5 niveles | Gratis solo para uso no comercial | Evitarla salvo que se confirme que el uso es compatible con la licencia. |
| Fuentes nacionales (IGN/SNIT, institutos nacionales), HDX COD-AB, OSM | Varía según el país | Varía según el país | Preferirlas cuando existan y su licencia lo permita. |

Las fuentes no coinciden en las zonas en disputa. Mostrar siempre la fuente, la versión y la licencia de la geometría que se usó.

## Requisitos por cada región nueva

1. **Geometría.** Fijar la fuente, la versión, el nivel, la fecha de acceso, la licencia y un hash. Documentar qué se hace con islas, zonas en disputa y componentes excluidos.
2. **Dos versiones de la geometría.** La completa se usa para el cálculo. La simplificada (GeoJSON, TopoJSON o PMTiles) se usa para el mapa. La interfaz no debe dar a entender que la versión simplificada es la del cálculo.
3. **IMERG.** Recortar con Harmony usando el rectángulo que contiene la región y después aplicar la máscara exacta. Documentar cómo se pesan las celdas que caen solo en parte dentro del polígono, el filtro de calidad (QI), el tratamiento de datos faltantes, el respaldo y la procedencia (ver `respaldo-recortes-supabase.md`).
4. **Ciencia.** Revisar el sesgo y la cobertura de IMERG en la zona: montaña, costa y latitud (la calidad baja por encima de 60°). Calcular la tendencia por región y no extrapolarla desde Costa Rica. Advertir cuando una región tiene pocas celdas. Si no se puede validar, el resultado se declara inconcluso.
5. **Contrato de la API** (por acordar). Añadir `GET /api/regions` con `id`, nombre, fuente, versión, licencia, `bbox` y la URL de la geometría simplificada. Pasar `region_id` en `POST /api/exploration`. Incluir la procedencia de la geometría en cada serie.
6. **Frontend.** Añadir un selector de región, ajustar el mapa a cada región con `fitBounds` y mostrar la atribución de cada capa, que CC BY exige. Si se cubren muchos países, servir los límites como teselas vectoriales (PMTiles).

## Recomendación

- Empezar con 2 o 3 países de Latinoamérica, preprocesados y versionados. La selección libre en todo el planeta sigue fuera de alcance.
- Usar geoBoundaries ADM0/ADM1 por defecto y la fuente nacional cuando esté disponible.

## Fuentes consultadas

- FAO GAUL 2024: https://www.fao.org/agroinformatics/training-and-resources/data-sets/data-set-detail/global-gaul-new-2024-release/en
- geoBoundaries (PLOS ONE): https://pmc.ncbi.nlm.nih.gov/articles/PMC7182183
- Natural Earth, licencia: https://www.naturalearthdata.com/?p=3348
- Ficha de GADM en Atlas: https://atlas.co/data-sources/global-administrative-areas/
- GAUL 2024 en Digital Public Goods: https://www.digitalpublicgoods.net/r/global-administrative-unit-layers-gaul-2024
