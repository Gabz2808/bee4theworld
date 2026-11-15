from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


class SupabaseConfigurationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    secret_key = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", supabase_url),
            ("SUPABASE_SECRET_KEY", secret_key),
        )
        if not value
    ]
    if missing:
        raise SupabaseConfigurationError(
            f"Faltan variables de entorno requeridas: {', '.join(missing)}"
        )

    return create_client(supabase_url, secret_key)
