"""Genera capas locales desde los recortes verificados; no descarga datos."""
import calendar
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import netCDF4
import numpy as np
from shapely.geometry import box, mapping, shape
from shapely.prepared import prep

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / 'apps/api/data/cache/imerg-snit-2001-2024-harmony-054695e5'
GEO = ROOT / 'datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz'
OUT = ROOT / 'apps/web/public/map-data'
EXPECTED = 'ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=OUT, help='Directorio nuevo para los derivados')
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError(f'El directorio de salida ya existe: {output}')
    geometry_bytes = gzip.decompress(GEO.read_bytes())
    if hashlib.sha256(geometry_bytes).hexdigest() != EXPECTED:
        raise ValueError('La geometría no coincide con la serie')
    geometry = shape(json.loads(geometry_bytes))
    manifest = json.loads((CACHE / 'manifest.json').read_text(encoding='utf-8'))
    prepared = prep(geometry)
    selected = None
    reference_grid = None
    months = []
    output.mkdir(parents=True)
    # Simplificación exclusivamente cartográfica; el análisis conserva la frontera original.
    (output / 'boundary.json').write_text(json.dumps(mapping(geometry.simplify(0.002, preserve_topology=True)), separators=(',', ':')), encoding='utf-8')
    for item in manifest['files']:
        path = CACHE / item['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f"Huella incorrecta: {item['file']}")
        year, month = map(int, item['month'].split('-'))
        with netCDF4.Dataset(path) as ds:
            grid = ds.groups['Grid']
            var = grid.variables['precipitation']
            if var.dimensions != ('time', 'lon', 'lat') or var.units != 'mm/hr':
                raise ValueError('Variable incompatible')
            time = grid.variables['time']
            t = netCDF4.num2date(time[:], time.units, calendar=getattr(time, 'calendar', 'standard'))
            if len(t) != 1 or (t[0].year, t[0].month) != (year, month):
                raise ValueError('Fecha incompatible')
            lon = np.asarray(grid.variables['lon_bnds'][:], dtype=float)
            lat = np.asarray(grid.variables['lat_bnds'][:], dtype=float)
            if selected is None:
                reference_grid = (lon.copy(), lat.copy())
                selected = [(x, y, [float(lon[x, 0]), float(lat[y, 0]), float(lon[x, 1]), float(lat[y, 1])]) for x in range(len(lon)) for y in range(len(lat)) if prepared.intersects(box(float(lon[x, 0]), float(lat[y, 0]), float(lon[x, 1]), float(lat[y, 1])))]
            elif not np.array_equal(lon, reference_grid[0]) or not np.array_equal(lat, reference_grid[1]):
                raise ValueError('Cuadrícula incompatible')
            values = np.ma.asarray(var[0, :, :])
            cells = []
            for x, y, bounds in selected:
                v = values[x, y]
                value = None if np.ma.is_masked(v) or not np.isfinite(v) or v < 0 else round(float(v) * 24 * calendar.monthrange(year, month)[1], 3)
                cells.append([*bounds, value])
            layer = json.dumps({'month': item['month'], 'cells': cells}, separators=(',', ':'), allow_nan=False).encode('utf-8')
            (output / (item['month'] + '.json')).write_bytes(layer)
            months.append({'month': item['month'], 'file': item['month'] + '.json', 'sha256': hashlib.sha256(layer).hexdigest(), 'source_file': item['file'], 'source_sha256': item['sha256']})
    boundary = (output / 'boundary.json').read_bytes()
    (output / 'manifest.json').write_text(json.dumps({
        'status': 'capa derivada para visualización; revisión científica y de distribución pendientes',
        'dataset': manifest['dataset'],
        'doi': '10.5067/GPM/IMERG/3B-MONTH/07',
        'source': 'NASA GES DISC / Harmony, recortes locales verificados por huella',
        'harmony_job_id': manifest['job_id'],
        'geometry_sha256': EXPECTED,
        'geometry_file': 'datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz',
        'geometry_attribution': 'IGN / Registro Nacional / SNIT',
        'source_units': 'mm/hr',
        'unit': 'mm/month',
        'unit_conversion': 'tasa mm/hr multiplicada por las horas del mes; redondeo a tres decimales',
        'cell_selection': 'celdas completas de la cuadrícula IMERG que intersectan la frontera; incluyen área fuera de ella',
        'cell_format': '[oeste, sur, este, norte, valor o null]',
        'boundary_file': 'boundary.json',
        'boundary_sha256': hashlib.sha256(boundary).hexdigest(),
        'boundary_simplification': 'shapely simplify 0.002° con topología preservada; solo visualización, el cálculo usa la frontera original',
        'months': months,
    }, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f"Generados {len(manifest['files'])} meses en {output}")


if __name__ == '__main__':
    main()
