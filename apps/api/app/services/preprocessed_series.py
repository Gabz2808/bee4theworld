"""Serie de demostración extraída previamente; no acredita validación científica."""
import json
import logging
from datetime import date
from pathlib import Path

from shapely.geometry import shape

from app.core.supabase_cache import CachedSeries, _rows_to_frame
from app.models.geojson import GeoJSONPolygon

logger = logging.getLogger(__name__)
SERIES = Path(__file__).resolve().parents[4] / "docs/evidencia/harmony-costa-rica-provisional-2001-2024.json"
GEOMETRY = {"type": "Polygon", "coordinates": [[[-85.95, 10.05], [-85.55, 11.10], [-84.80, 11.00], [-83.60, 10.75], [-82.60, 9.55], [-82.85, 8.35], [-83.65, 8.50], [-84.90, 9.50], [-85.45, 9.85], [-85.95, 10.05]]]}


def load_preprocessed_series(public_id: str, geom: GeoJSONPolygon, start: date, end: date) -> CachedSeries | None:
    if public_id != "costa-rica-continental" or not shape(geom.model_dump(mode="json")).equals(shape(GEOMETRY)):
        return None
    try:
        data = json.loads(SERIES.read_text(encoding="utf-8"))
        meta = data["metadata"]
        selection = meta["selection"]
        period = selection["effective_period"]
        full_start, full_end = date.fromisoformat(period["start"]), date.fromisoformat(period["end"])
        if (data["status"] != "success" or meta["dataset"] != "GPM_3IMERGM.07" or meta["unit"] != "mm/month"
            or meta["source_units"] != "mm/hr" or selection["region_id"] != public_id
            or selection["boundary_version"] != "provisional" or start < full_start or end > full_end):
            return None
        rows = [{"observed_month": point["date"], "precipitation_mm": point["value"], "coverage_fraction": point["coverage_fraction"], "quality_flag": point["quality_flag"]} for point in data["timeseries"]]
        frame = _rows_to_frame(rows, full_start, full_end)
        ids = meta["source_granule_ids"]
        if frame is None or len(ids) != len(frame) or len(set(ids)) != len(ids) or not all(isinstance(x, str) and x for x in ids):
            return None
        selected = frame.loc[start.isoformat():end.isoformat()].copy()
        indexes = [i for i, month in enumerate(frame.index) if start <= month.date() <= end]
        return CachedSeries(selected, {**meta, "created_at": meta["data_accessed_at"], "source_granule_ids": [ids[i] for i in indexes]})
    except (OSError, ValueError, TypeError, KeyError):
        logger.warning("La serie preprocesada no está disponible o es incompatible.")
        return None
