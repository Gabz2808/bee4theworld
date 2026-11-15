# Revisión de la serie SNIT para el issue #8

15 de noviembre de 2026. Manuel informó que Gabriel aceptó esta serie SNIT concreta para el MVP y el alcance de los issues #7 y #8. La aceptación de uso no constituye validación científica del producto.

## Geometría y trazabilidad

- `capturar_frontera_snit.py verify` confirmó las huellas de la captura provincial, siete provincias y EPSG:4326. Al unir las geometrías archivadas y comparar topológicamente, el archivo continental derivado es igual al componente de mayor área; la unión tiene 121 componentes y la geometría derivada es válida. Esto comprueba la derivación de la captura, no la exactitud de la frontera ni la clasificación individual de los 120 componentes excluidos. El ámbito operativo fue decidido por Manuel; su revisión científica conjunta sigue pendiente.
- La huella SHA-256 del GeoJSON continental descomprimido es `ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb` y coincide con la declarada por la serie. La API comprueba también la huella canónica de la serie y sus 288 identificadores y meses. Las huellas vinculan archivos, pero no prueban por sí solas el origen de los valores.
- El procesamiento registra `GPM_3IMERGM.07`, colección `C2723754851-GES_DISC`, DOI [10.5067/GPM/IMERG/3B-MONTH/07](https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07) y un trabajo Harmony. El script contrasta los identificadores con CMR y una extracción anterior; el manifiesto local acredita las huellas de los recortes. Los identificadores no se verificaron independientemente contra cada archivo original en esta revisión. La comparación de un mes mediante otra extracción empleó el mismo agregador de la API.

## Valores, unidades y cobertura

Se ejecutó `.venv/Scripts/python.exe scripts/revisar_serie_snit_independiente.py` desde `apps/api`. El script lee los 288 recortes locales, verifica sus huellas y meses, y calcula por separado las intersecciones en EPSG:6933 sin llamar al agregador de la API. Con las coordenadas originales reproduce los 288 valores de la serie con diferencia absoluta máxima de `1,71 × 10⁻¹³ mm/mes`. Comparte fuente, geometría y biblioteca geoespacial con el procesamiento original: es un contraste de implementación, no una validación independiente de las observaciones.

La [documentación técnica de IMERG](https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_TechnicalDocumentation_final_230713.pdf) describe el valor mensual como tasa media del mes calendario. Los recortes declaran `mm/hr`; multiplicar esa tasa por las horas del mes es coherente para expresar el acumulado estimado en `mm/month`, incluyendo la duración variable de febrero. Esto no certifica por sí solo la calidad de la estimación.

Las coordenadas originales contienen pequeñas variaciones de precisión. Las celdas construidas alrededor de esos centros dejan huecos y solapamientos diminutos: la suma de áreas intersectadas equivale a `0,9999979013` del área regional, mientras el área no cubierta por la **unión** de celdas es aproximadamente `0,000016085` del área regional. Al regularizar los centros a la cuadrícula nominal de 0,1° para un contraste, la cobertura calculada es `0,9999999999999586` y la diferencia absoluta máxima de los valores es `0,0003052 mm/mes` (mediana `0,0000660`). Este experimento apunta a precisión de coordenadas como causa de la cobertura parcial casi total; no autoriza cambiar la serie ni prueba la ausencia de otros problemas. El backend marca como parcial cualquier cobertura menor que 1; la regla y cualquier tolerancia deben revisarse con el compañero.

Los valores `ok` y `partial_coverage` de esta serie son etiquetas derivadas de cobertura espacial por el procesamiento local, no el índice de calidad de NASA. No se aplicó un filtro basado en `precipitationQualityIndex`; la [guía NASA para IMERG V07](https://gpm.nasa.gov/sites/default/files/2025-02/FAQ%20for%20IMERG%20V07%20Applications%20Users_202502.pdf) describe ese índice por separado y advierte sobre su agregación y los cambios de sensores para estudios de largo plazo.

## Revisiones científicas pendientes

1. Revisar con el compañero la geometría, exclusiones, condiciones de distribución, procedencia de los recortes y correspondencia de identificadores con los archivos fuente.
2. Acordar y revisar el método de agregación, el tratamiento de precisión de coordenadas, cobertura y calidad; contrastar con Giovanni u otra referencia para una región y configuración equivalentes, explicitando diferencias metodológicas.
3. Revisar incertidumbre y sesgos de IMERG y la metodología de tendencias por separado. El frontend mantiene el resultado sin validar y oculta la interpretación estadística.

La comprobación funcional y los casos sintéticos de valores faltantes están documentados en [frontend.md](frontend.md). La aceptación para el MVP permite evaluar el cierre funcional del issue #8 sin dar por resueltas estas revisiones.
