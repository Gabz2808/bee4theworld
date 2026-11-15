import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import backup_recortes_supabase as backup


class BackupTests(unittest.TestCase):
    def sample(self):
        raw = b"datos de prueba"
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as tar:
            info = tarfile.TarInfo("month.nc4")
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
        archive = stream.getvalue()
        manifest = {"source": "prueba", "harmony_job_id": "job", "dataset": "test", "archives": [{"file": "2001.tar", "bytes": len(archive), "sha256": backup.sha(archive)}], "files": [{"file": "month.nc4", "bytes": len(raw), "sha256": backup.sha(raw)}]}
        encoded = json.dumps(manifest).encode()
        return encoded, archive, raw

    def test_restore_checks_objects_without_local_source(self):
        manifest, archive, raw = self.sample()
        class Bucket:
            def download(self, path): return manifest if path.endswith("manifest.json") else archive
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "restored"
            with patch.object(backup, "MANIFEST_SHA256", backup.sha(manifest)), patch.object(backup, "RESTORED", target), patch.object(backup, "client"), patch.object(backup, "checked_bucket", return_value=Bucket()):
                backup.verify(restore=True)
                self.assertEqual((target / "month.nc4").read_bytes(), raw)
                with self.assertRaises(FileExistsError):
                    backup.verify(restore=True)

    def test_verification_rejects_modified_archive(self):
        manifest, archive, _ = self.sample()
        class Bucket:
            def download(self, path): return manifest if path.endswith("manifest.json") else archive + b"changed"
        with patch.object(backup, "MANIFEST_SHA256", backup.sha(manifest)), patch.object(backup, "client"), patch.object(backup, "checked_bucket", return_value=Bucket()):
            with self.assertRaises(ValueError):
                backup.verify()


if __name__ == "__main__":
    unittest.main()
