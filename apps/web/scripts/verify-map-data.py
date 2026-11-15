"""Verifica las capas del mapa contra los recortes IMERG y la serie regional; no descarga datos.

Comprobaciones:
1. Manifiesto: producto, huella de geometría y huellas de cada capa.
2. Cada celda de cada capa coincide con el valor NetCDF original convertido a mm/mes.
3. El promedio ponderado por área (EPSG:6933) de las celdas, recalculado aquí de forma
   independiente con la frontera original, reproduce la serie regional versionada.
4. Se cuantifica la diferencia de la frontera simplificada usada solo para visualización.
"""
import argparse
import calendar
import gzip
import hashlib
import json
from pathlib import Path

import netCDF4
import numpy as np
from pyproj import Transformer
import shapely
from shapely.geometry import box, shape

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / 'apps/api/data/cache/imerg-snit-2001-2024-harmony-054695e5'
GEO = ROOT / 'datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz'
SERIES = ROOT / 'datos/procesados/imerg-snit-continental-2001-2024-cache-v1.json'
LAYERS = ROOT / 'apps/web/public/map-data'
EXPECTED = 'ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb'
CELL_TOLERANCE = 0.0005 + 1e-9  # redondeo a tres decimales de la capa
REGIONAL_TOLERANCE = 0.01  # mm/mes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--layers', type=Path, default=LAYERS)
    parser.add_argument('--report', type=Path, help='Ruta opcional para guardar el informe JSON')
    layers = parser.parse_args().layers
    report_path = parser.parse_args().report

    geometry_bytes = gzip.decompress(GEO.read_bytes())
    assert hashlib.sha256(geometry_bytes).hexdigest() == EXPECTED, 'Huella de geometría distinta'
    geometry = shape(json.loads(geometry_bytes))
    projector = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)

    def to_area(geom):
        return shapely.transform(geom, lambda c: np.column_stack(projector.transform(c[:, 0], c[:, 1])))

    geometry_area = to_area(geometry)

    manifest = json.loads((layers / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['dataset'] == 'GPM_3IMERGM.07', 'Producto distinto'
    assert manifest['geometry_sha256'] == EXPECTED, 'Manifiesto con otra geometría'
    series = {p['date'][:7]: p for p in json.loads(SERIES.read_text(encoding='utf-8'))['timeseries']}
    cache = {item['month']: item for item in json.loads((CACHE / 'manifest.json').read_text(encoding='utf-8'))['files']}
    assert set(series) == set(cache) == {m['month'] for m in manifest['months']}, 'Meses distintos'

    weights = None
    max_cell_error = 0.0
    max_regional_error = 0.0
    worst_month = None
    null_cells = 0
    for entry in manifest['months']:
        month = entry['month']
        layer_bytes = (layers / entry['file']).read_bytes()
        assert hashlib.sha256(layer_bytes).hexdigest() == entry['sha256'], f'Huella de capa distinta: {month}'
        layer = json.loads(layer_bytes)
        assert layer['month'] == month
        cells = layer['cells']
        if weights is None:
            weights = [to_area(box(w, s, e, n)).intersection(geometry_area).area for w, s, e, n, _ in cells]
            assert all(a > 0 for a in weights), 'Celda sin intersección'
        assert len(cells) == len(weights), f'Número de celdas distinto: {month}'

        item = cache[month]
        path = CACHE / item['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], f'Recorte alterado: {month}'
        year, number = map(int, month.split('-'))
        hours = 24 * calendar.monthrange(year, number)[1]
        with netCDF4.Dataset(path) as ds:
            grid = ds.groups['Grid']
            lon = np.asarray(grid.variables['lon'][:], dtype=float)
            lat = np.asarray(grid.variables['lat'][:], dtype=float)
            values = np.ma.asarray(grid.variables['precipitation'][0, :, :])
            for w, s, e, n, value in cells:
                x = int(np.argmin(np.abs(lon - (w + e) / 2)))
                y = int(np.argmin(np.abs(lat - (s + n) / 2)))
                raw = values[x, y]
                if np.ma.is_masked(raw) or not np.isfinite(raw) or raw < 0:
                    assert value is None, f'Celda sin dato con valor: {month}'
                    null_cells += 1
                    continue
                max_cell_error = max(max_cell_error, abs(float(raw) * hours - value))

        valid = [(c[4], a) for c, a in zip(cells, weights) if c[4] is not None]
        expected = series[month]['value']
        if expected is None:
            assert not valid, f'La serie no tiene dato y la capa sí: {month}'
            continue
        regional = sum(v * a for v, a in valid) / sum(a for _, a in valid)
        error = abs(regional - expected)
        if error > max_regional_error:
            max_regional_error, worst_month = error, month

    simplified = shape(json.loads((layers / 'boundary.json').read_text(encoding='utf-8')))
    simplified_area = to_area(simplified)
    report = {
        'months': len(manifest['months']),
        'cells_per_month': len(weights),
        'null_cells': null_cells,
        'max_cell_error_mm_month': max_cell_error,
        'max_regional_error_mm_month': max_regional_error,
        'worst_regional_month': worst_month,
        'boundary_area_km2': geometry_area.area / 1e6,
        'simplified_area_difference_pct': 100 * geometry_area.symmetric_difference(simplified_area).area / geometry_area.area,
        'simplified_hausdorff_deg': geometry.hausdorff_distance(simplified),
    }
    assert max_cell_error <= CELL_TOLERANCE, f'Error de celda {max_cell_error}'
    assert max_regional_error <= REGIONAL_TOLERANCE, f'Error regional {max_regional_error} en {worst_month}'
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report_path:
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Verificación OK')


if __name__ == '__main__':
    main()
