import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import capturar_frontera_snit as snapshot


def example():
    polygon = {"type": "Polygon", "coordinates": [[[-85, 9], [-84, 9], [-84, 10], [-85, 9]]]}
    return {"type": "FeatureCollection", "numberMatched": 7,
            "crs": {"properties": {"name": "urn:ogc:def:crs:EPSG::4326"}},
            "features": [{"type": "Feature", "properties": {"PROVINCIA": name}, "geometry": polygon} for name in snapshot.PROVINCES]}


class SnapshotTests(unittest.TestCase):
    def test_rejects_incomplete_and_invalid_geometry(self):
        data = example()
        data["features"].pop()
        with self.assertRaises(ValueError):
            snapshot.validate(json.dumps(data).encode())
        data = example()
        data["features"][0]["geometry"] = {"type": "Point", "coordinates": [-84, 10]}
        with self.assertRaises(ValueError):
            snapshot.validate(json.dumps(data).encode())

    def test_capture_is_immutable_and_detects_tampering(self):
        class Response:
            content = json.dumps(example(), ensure_ascii=False).encode()
            def raise_for_status(self): pass
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, meta = root / "data.gz", root / "metadata.json"
            with patch.object(snapshot, "ROOT", root), patch.object(snapshot, "DATA", data), patch.object(snapshot, "META", meta), patch.object(snapshot.httpx, "get", return_value=Response()):
                snapshot.capture()
                snapshot.verify()
                with self.assertRaises(FileExistsError):
                    snapshot.capture()
                data.write_bytes(data.read_bytes() + b"tampered")
                with self.assertRaises(ValueError):
                    snapshot.verify()


if __name__ == "__main__":
    unittest.main()
