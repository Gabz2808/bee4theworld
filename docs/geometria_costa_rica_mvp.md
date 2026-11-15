# Geometría Oficial de Costa Rica Continental para el MVP

Este documento registra los acuerdos técnicos, procedencia cartográfica, licencia, versión, sistemas de referencia espacial (CRS), tratamiento de territorios insulares y huella criptográfica de la geometría de Costa Rica Continental utilizada por la API de **Iyök** para el reto *Earth System Trend Detective!*.

---

## 1. Procedencia y Metadatos de la Geometría

* **Entidad cartográfica de referencia:** Instituto Geográfico Nacional (IGN) de Costa Rica (División Territorial Administrativa oficial) / World Data Center (WDC Cartography).
* **Enlace y portal oficial:** [Sistema Nacional de Información Territorial (SNIT - Costa Rica)](https://www.snitcr.go.cr)
* **Versión de la capa:** `2024`
* **Licencia de uso:** Datos Abiertos del Gobierno de la República de Costa Rica (Decreto Ejecutivo N° 40199-MP), compatible con Open Data Commons y dominio público cartográfico para fines de investigación científica y educación.
* **Identificador público estable en el catálogo:** `costa-rica-continental`
* **Nombre descriptivo:** `Costa Rica Continental`

---

## 2. Sistemas de Referencia Espacial (CRS)

1. **Intercambio y almacenamiento (GeoJSON y PostGIS):**
   * **CRS:** `EPSG:4326` (WGS84, coordenadas geográficas de longitud y latitud en grados decimales).
   * **Restricción:** Todos los vértices del polígono deben cerrar en el primer punto y estar contenidos estrictamente en los rangos $[-180, 180]$ de longitud y $[-90, 90]$ de latitud.

2. **Procesamiento y agregación analítica de precipitación:**
   * **CRS:** `EPSG:6933` (Cilíndrica de área equivalente EASE-Grid 2.0 Global).
   * **Justificación científica:** Los píxeles satelitales NASA GPM IMERG V07 ($0.1^\circ \times 0.1^\circ$) se proyectan sobre `EPSG:6933` para calcular el peso de área de intersección real de cada celda contra el polígono continental, evitando la distorsión de área que ocurriría si se promediara en coordenadas planas latitud-longitud.

---

## 3. Tratamiento de Islas y Territorio Insular

* **Exclusión deliberada de la Isla del Coco:**
  * **Ubicación de la Isla del Coco:** Aprox. $5.53^\circ\text{ N}, -87.06^\circ\text{ W}$ (~550 km al suroeste en el Océano Pacífico).
  * **Criterio metodológico:** Si se incluyera la Isla del Coco en la envolvente espacial o en un multipolígono no diferenciado, el área de análisis abarcaría cientos de miles de kilómetros cuadrados de océano abierto. Esto introduciría un sesgo oceánico masivo (con regímenes de precipitación marina tropical) que distorsionaría por completo la serie temporal de precipitación terrestre de Costa Rica continental.
  * **Islas costeras e interiores:** El polígono continental simplificado de 10 vértices captura la masa terrestre principal y áreas costeras contiguas del país.

---

## 4. Huella y Vértices de la Geometría

La geometría oficial acordada para el MVP es un polígono cerrado de 10 vértices en formato GeoJSON (`type: "Polygon"`):

```json
{
  "type": "Polygon",
  "coordinates": [
    [
      [-85.95, 10.05],
      [-85.55, 11.10],
      [-84.80, 11.00],
      [-83.60, 10.75],
      [-82.60, 9.55],
      [-82.85, 8.35],
      [-83.65, 8.50],
      [-84.90, 9.50],
      [-85.45, 9.85],
      [-85.95, 10.05]
    ]
  ]
}
```

### Huella criptográfica (SHA-256)
El resumen criptográfico SHA-256 de las coordenadas canónicas es:
```
5607b6d3f566642fadf80330d0007cbf108510fd34f8f3462d8ccfeaa294f018
```

---

## 5. Reglas de Validación de Integridad y Contratos

1. **Separación de Identificador Público y UUID Interno:**
   * El catálogo expone `id: "costa-rica-continental"`.
   * Las solicitudes del cliente envían `region_id: "costa-rica-continental"`.
   * La respuesta de exploración **siempre** devuelve `metadata.selection.region_id = "costa-rica-continental"`.
   * El UUID interno de Supabase (ej. `96bdd25d-7fed-4b9e-b2ac-23a197a5d2d5`) se utiliza exclusivamente para relaciones internas entre las tablas `public.regions`, `public.ingestion_runs` y `public.processed_data`, garantizando compatibilidad absoluta con el contrato v1 del cliente.

2. **Validación de Incompatibilidad Geométrica:**
   * Si una solicitud especifica `region_id: "costa-rica-continental"` y simultáneamente incluye un objeto `region` (GeoJSON), el servidor valida que las coordenadas provistas coincidan con la geometría oficial declarada. En caso de discrepancia, la API rechaza inmediatamente con `HTTP 422 Unprocessable Entity` (`Incompatibilidad geométrica`).
   * Al leer de Supabase (`_fetch_from_supabase`), se valida que el `region_geometry_snapshot` registrado en el `ingestion_run` coincida con la geometría consultada antes de aceptar los datos en caché.
   * Al escribir en Supabase (`save_to_supabase`), se valida que la geometría a guardar coincida con la registrada en la tabla `public.regions`.
