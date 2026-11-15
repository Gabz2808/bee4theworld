"""Respaldo privado, idempotente y verificable de los recortes IMERG del MVP.

Desde apps/api: python scripts/backup_recortes_supabase.py prepare|upload|verify|restore
Las credenciales se cargan exclusivamente desde el entorno o .env local.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from supabase import create_client

API = Path(__file__).resolve().parents[1]
CACHE = API / "data/cache/imerg-snit-2001-2024-harmony-054695e5"
STAGING = API / "data/cache/backup-supabase-imerg-snit-v1"
RESTORED = API / "data/cache/restaurado-imerg-snit-v1"
BUCKET = "iyok-imerg-backups"
PREFIX = "gpm-3imergm-v07/snit-continental/2001-2024/054695e5-f58a-47f6-a365-bf600d9d0b6d"
EXPECTED_HOST = "avtptwxgfuflmktfhgtk.supabase.co"
LIMIT = 2 * 1024 * 1024
MANIFEST_SHA256 = "b45283e4e7d0904a85c32a31403fec105d7081592631b63bab3b7c31c28c6fd4"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prepare() -> dict:
    original = json.loads((CACHE / "manifest.json").read_text(encoding="utf-8"))
    entries = original["files"]
    months = [f"{y:04}-{m:02}" for y in range(2001, 2025) for m in range(1, 13)]
    if len(entries) != 288 or sorted(e["month"] for e in entries) != months:
        raise ValueError("El manifiesto no contiene exactamente 288 meses únicos")
    if original["dataset"] != "GPM_3IMERGM.07" or original["job_id"] != PREFIX.rsplit("/", 1)[-1]:
        raise ValueError("El manifiesto no corresponde a esta colección")
    STAGING.mkdir(parents=True, exist_ok=True)
    archives = []
    for year in range(2001, 2025):
        subset = sorted((e for e in entries if e["month"].startswith(str(year))), key=lambda e: e["month"])
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w") as tar:
            for e in subset:
                name = e["file"]
                if Path(name).name != name or not name.endswith(".nc4"):
                    raise ValueError("Nombre de archivo inválido")
                raw = (CACHE / name).read_bytes()
                if len(raw) != e["bytes"] or sha(raw) != e["sha256"]:
                    raise ValueError(f"El archivo no coincide con el manifiesto: {name}")
                info = tarfile.TarInfo(name)
                info.size, info.mtime, info.mode, info.uid, info.gid = len(raw), 0, 0o600, 0, 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(raw))
        raw = buffer.getvalue()
        if len(raw) > LIMIT:
            raise ValueError("Archivo anual supera el límite de tamaño del bucket")
        name = f"{year}.tar"
        target = STAGING / name
        if target.exists() and target.read_bytes() != raw:
            raise ValueError(f"Existe un archivo local distinto: {name}")
        if not target.exists():
            target.write_bytes(raw)
        archives.append({"file": name, "bytes": len(raw), "sha256": sha(raw), "months": [e["month"] for e in subset]})
    manifest = {"format": "iyok-imerg-backup-v1", "source": original["source"], "dataset": original["dataset"],
                "harmony_job_id": original["job_id"], "verified_at_utc": original["verified_at_utc"],
                "geometry_sha256": "ea5ab8413ca2b1af4fc6602cffd08ae4e2c956a6d901a45e2ece4dbd25c6cfcb",
                "coverage_note": "Recortes espaciales Harmony, no gránulos globales completos.", "archives": archives, "files": entries}
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if sha(encoded) != MANIFEST_SHA256:
        raise ValueError("El manifiesto no coincide con la versión de respaldo fijada")
    target = STAGING / "manifest.json"
    if target.exists() and target.read_bytes() != encoded:
        raise ValueError("El manifiesto local existente es diferente")
    if not target.exists():
        target.write_bytes(encoded)
    return manifest


def client():
    load_dotenv(API / ".env")
    url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_SECRET_KEY", "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != EXPECTED_HOST or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("El destino Supabase no coincide con el proyecto verificado")
    if not key:
        raise ValueError("Falta SUPABASE_SECRET_KEY en el entorno del servidor")
    return create_client(url, key)


def checked_bucket(s, *, create: bool):
    buckets = [b for b in s.storage.list_buckets() if b.name == BUCKET]
    if not buckets and create:
        s.storage.create_bucket(BUCKET, options={"public": False, "file_size_limit": LIMIT, "allowed_mime_types": ["application/x-tar", "application/json"]})
        buckets = [b for b in s.storage.list_buckets() if b.name == BUCKET]
    if len(buckets) != 1 or buckets[0].public:
        raise ValueError("El bucket no existe o no es privado")
    return s.storage.from_(BUCKET)


def upload():
    manifest = prepare()
    bucket = checked_bucket(client(), create=True)
    # El manifiesto se escribe al final: su presencia indica que todos los archivos fueron verificados.
    for record in [*manifest["archives"], {"file": "manifest.json", "sha256": sha((STAGING / "manifest.json").read_bytes())}]:
        name, expected = record["file"], record["sha256"]
        raw = (STAGING / name).read_bytes()
        path = f"{PREFIX}/{name}"
        try:
            bucket.upload(path, raw, file_options={"content-type": "application/json" if name.endswith(".json") else "application/x-tar", "upsert": "false"})
        except Exception as exc:
            # Una repetición solo es válida si el objeto existente coincide byte a byte.
            try:
                existing = bucket.download(path)
            except Exception:
                raise RuntimeError(f"No se pudo subir ni verificar {name}") from exc
            if sha(existing) != expected:
                raise ValueError(f"Existe un objeto diferente: {name}") from exc
        if sha(bucket.download(path)) != expected:
            raise ValueError(f"La verificación remota falló: {name}")
        print(f"Verificado: {name}", flush=True)


def verify(*, restore: bool = False):
    bucket = checked_bucket(client(), create=False)
    remote_manifest = bucket.download(f"{PREFIX}/manifest.json")
    if sha(remote_manifest) != MANIFEST_SHA256:
        raise ValueError("El manifiesto remoto no coincide con la huella fijada")
    expected = json.loads(remote_manifest.decode("utf-8"))
    entries = {entry["file"]: entry for entry in expected["files"]}
    if restore:
        if RESTORED.exists():
            raise FileExistsError("La carpeta de restauración ya existe; no se sobrescribe")
        RESTORED.mkdir(parents=True)
    seen = set()
    for archive in expected["archives"]:
        raw = bucket.download(f"{PREFIX}/{archive['file']}")
        if len(raw) != archive["bytes"] or sha(raw) != archive["sha256"]:
            raise ValueError(f"Archivo remoto alterado: {archive['file']}")
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            for member in tar.getmembers():
                if not member.isfile() or Path(member.name).name != member.name or member.name in seen or member.name not in entries:
                    raise ValueError("Contenido de archivo anual inválido")
                data = tar.extractfile(member).read()
                entry = entries[member.name]
                if len(data) != entry["bytes"] or sha(data) != entry["sha256"]:
                    raise ValueError(f"Recorte alterado: {member.name}")
                seen.add(member.name)
                if restore:
                    (RESTORED / member.name).write_bytes(data)
    if seen != set(entries):
        raise ValueError("El respaldo no contiene todos los recortes")
    if restore:
        (RESTORED / "manifest.json").write_text(json.dumps({"source": expected["source"], "job_id": expected["harmony_job_id"], "dataset": expected["dataset"], "files": expected["files"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Respaldo íntegro: {len(expected['archives'])} archivos anuales, {len(seen)} recortes" + (f"; restaurados en {RESTORED}" if restore else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "upload", "verify", "restore"))
    action = parser.parse_args().action
    if action == "prepare":
        print(f"Preparados {len(prepare()['archives'])} archivos anuales; sin cambios remotos")
    elif action == "upload":
        upload()
    else:
        verify(restore=action == "restore")
