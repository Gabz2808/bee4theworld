"""Serie mensual fija y geometría SNIT identificada por huella, sin consulta remota."""
import gzip
import hashlib
import json
import logging
import zlib
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.core.supabase_cache import CachedSeries, _rows_to_frame

ROOT = Path(__file__).resolve().parents[4]
SERIES = ROOT / "datos/procesados/imerg-snit-continental-2001-2024-cache-v1.json"
GEOMETRY = ROOT / "datos/fuentes/snit-provincial-2026-11-15/continental-principal.geojson.gz"
REGION_ID = "costa-rica-snit-continental-v1"
GEOMETRY_SHA = "ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb"
SERIES_SHA = "43908fb5a7b7faa94cf9d7fde99845954d3505b0d19a70eb1dcfca51fc746be6"
START, END = date(2001, 1, 1), date(2024, 12, 31)
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _read(series_path: Path, geometry_path: Path, signatures: tuple[int, int, int, int]) -> CachedSeries:
    del signatures
    data = json.loads(series_path.read_text(encoding="utf-8"))
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != SERIES_SHA:
        raise ValueError("Huella de serie incompatible")
    if hashlib.sha256(gzip.decompress(geometry_path.read_bytes())).hexdigest() != GEOMETRY_SHA:
        raise ValueError("Huella de geometría incompatible")
    if data["geometry"]["geometry_sha256"] != GEOMETRY_SHA or data["dataset"] != "GPM_3IMERGM.07" or data["unit"] != "mm/month" or data["source_units"] != "mm/hr":
        raise ValueError("Procedencia incompatible")
    ids = data["granule_ids"]
    if len(ids) != 288 or len(set(ids)) != 288 or not all(isinstance(i, str) and i for i in ids):
        raise ValueError("Gránulos incompatibles")
    rows = [{"observed_month": p["date"], "precipitation_mm": p["value"], "coverage_fraction": p["coverage_fraction"], "quality_flag": p["quality_flag"]} for p in data["timeseries"]]
    frame = _rows_to_frame(rows, START, END)
    if frame is None:
        raise ValueError("Serie incompleta o incompatible")
    return CachedSeries(frame, {**data, "source_granule_ids": ids})


def load_snit(start: date = START, end: date = END) -> CachedSeries | None:
    if start < START or end > END or start > end:
        return None
    try:
        s, g = SERIES.stat(), GEOMETRY.stat()
        full = _read(SERIES, GEOMETRY, (s.st_mtime_ns, s.st_size, g.st_mtime_ns, g.st_size))
        frame = full.frame.loc[start.isoformat():end.isoformat()].copy()
        indices = [i for i, month in enumerate(full.frame.index) if start <= month.date() <= end]
        return CachedSeries(frame, {**full.metadata, "source_granule_ids": [full.metadata["source_granule_ids"][i] for i in indices]})
    except (OSError, ValueError, KeyError, TypeError, EOFError, zlib.error):
        logger.warning("Serie SNIT o geometría no disponibles o incompatibles")
        return None
