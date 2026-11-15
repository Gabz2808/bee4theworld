# Traspaso de desarrollo: mapa del issue #11

Fecha: 15 de noviembre de 2026. Estado: mapa y control temporal implementados y verificados localmente; pendientes de revisión del equipo, de condiciones de distribución y de validación científica. No considerar el issue cerrado sin esa revisión.

## Solicitud y alcance

Manuel pidió conservar la vista actual y añadir una pestaña «Mapa» junto a «Serie temporal». Adjuntó tres referencias visuales con mapa protagonista, paneles y control temporal. Mantener la dirección natural y científica de Iyök, la incertidumbre y la distinción entre imagen de contexto y datos analíticos. No desplegar ni modificar la configuración pública.

## Implementación

- `maplibre-gl` 6.18 en el manifiesto y lockfile de `apps/web`; ECharts se mantiene. La instalación informó ocho vulnerabilidades moderadas en el árbol completo; no se clasificaron.
- `src/app/ui/explorer.tsx`: pestañas accesibles de serie y mapa (flechas izquierda/derecha); la serie es la pestaña inicial. El mes seleccionado se comparte y la gráfica lo marca.
- `src/app/ui/precipitation-map.tsx`:
  - Comprueba que la respuesta del servicio y `public/map-data/manifest.json` declaren `GPM_3IMERGM.07` y la huella de geometría `ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb`; si no coinciden, no pide ni dibuja capas y desactiva la reproducción.
  - Al cambiar de mes retira la capa anterior, muestra «Cargando la capa de…» y anuncia errores en una región `status`. La reproducción avanza solo cuando la capa del mes actual terminó de dibujarse y se detiene ante un error.
  - Deslizador con `aria-valuetext` del mes; reproducir desde el último mes reinicia en el primero.
  - Al seleccionar una celda se muestra su valor. Bajo la línea del producto, una nota discreta aclara que cada celda es una estimación satelital de su área, no una medición puntual.
  - Leyenda con las mismas posiciones relativas que los cortes de color (0, 100, 300, 600 y ≥1.000 mm/mes). El 99 % de los valores por celda de 2001–2024 es inferior a 644 mm/mes; el máximo es 1.321 mm/mes.
  - Atribución visible (no compacta) de IMERG/NASA GES DISC, frontera IGN/Registro Nacional/SNIT y OpenStreetMap. Gestos cooperativos para no secuestrar el desplazamiento de la página; textos de MapLibre en español.
  - Si falla el fondo de OSM, lo informa y mantiene celdas y frontera.
- `scripts/generate-map-data.py`: comprueba huellas de frontera y recortes, fecha, dimensiones, unidades y cuadrícula; convierte mm/h a mm/mes con las horas del mes (igual que el backend). Ahora escribe `manifest.json` con producto, DOI, trabajo Harmony, huellas de geometría, frontera simplificada, capas y recortes de origen, conversión y método. Se regeneró en un directorio nuevo: las 288 capas y la frontera fueron idénticas byte a byte a las existentes; solo se añadió el manifiesto.
- `scripts/verify-map-data.py`: verificación independiente (véase abajo).
- `tests/map.mjs`: prueba de navegador.

## Verificación realizada

| Comprobación | Resultado |
| --- | --- |
| Celdas de las 288 capas contra el NetCDF de cada mes, convertido a mm/mes | Error máximo 0,00011 mm/mes (redondeo a tres decimales); 520 celdas por mes, ninguna sin dato |
| Promedio ponderado por el área dentro de la frontera original (EPSG:6933), recalculado desde las capas, contra la serie regional versionada | Error máximo 0,00008 mm/mes (2016-11) |
| Frontera simplificada frente a la original | 0,20 % de diferencia de área; distancia de Hausdorff 0,002° |
| `npm run lint`, `npm run build`, pruebas unitarias del cliente (12), backend (146) y `tests/explorer-snit.mjs` | Pasan |
| `tests/map.mjs` a 1280 y 390 px con la API local | Carga de enero de 2024 y promedio 70,4 mm/mes; flechas en pestañas; deslizador con teclado (flecha y Fin); reproducción y pausa; la serie refleja el mes elegido; sin desbordamiento horizontal |
| Estados sintéticos en `tests/map.mjs` | Fondo OSM bloqueado, capa ausente (404) y manifiesto con otra geometría |

Resultado guardado en `docs/evidencia/verificacion-mapa-issue-11.json`. Reproducir desde la raíz:

```powershell
apps/api/.venv/Scripts/python.exe apps/web/scripts/verify-map-data.py
```

En capturas a 1280 y 390 px el territorio completo cabe en el encuadre inicial, con margen inferior para la atribución. El fondo OSM respondió en esta sesión. La verificación demuestra que las capas corresponden a los recortes y reproducen la serie; no valida la estimación IMERG ni la tendencia.

## Pendientes

- Revisar con Gabriel la relación entre celdas completas, frontera y promedio, y las condiciones de redistribución de los derivados NASA e IGN/SNIT antes de publicar `public/map-data/` (unos 11 MB, 289 archivos).
- El fondo usa `tile.openstreetmap.org`. Su [política de uso](https://operations.osmfoundation.org/policies/tiles/) exige atribución visible y no ofrece garantía de servicio; para mayor tráfico o una demo sin conexión, valorar otro proveedor o un fondo propio.
- Mantener `public/maplibre-gl-worker.mjs` idéntico a `node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs` al actualizar la dependencia (hoy coinciden).
- Corregido durante la integración: al subir `MIN_SUPPORTED_DATE` a 1998 en #20, la combinación SNIT del catálogo pasó a anunciarse como verificada para 1998–2024, aunque la serie reprocesada solo cubre 2001–2024 y una exploración de 1998 respondía `503 SNIT_SERIES_UNAVAILABLE`. Ahora el catálogo usa el rango de `snit_series` y una solicitud SNIT fuera de 2001–2024 responde `400 INVALID_REQUEST` sin consultar NASA (pruebas en `apps/api/tests/test_snit_exploration.py`). Revisar con Gabriel; la consulta NASA en vivo desde 1998 no cambia. Las capas del mapa solo cubren 2001–2024.
- La generación no sobrescribe un directorio existente: para regenerar usar `--output` con un directorio nuevo y comparar.
