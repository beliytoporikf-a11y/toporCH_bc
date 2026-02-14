from __future__ import annotations

from app.config import settings


def get_storage():
    provider = (settings.storage_provider or "").lower()
    if provider == "supabase":
        from app.storage_supabase import SupabaseStorage

        return SupabaseStorage()
    if provider == "gdrive":
        from app.storage_google_drive import GoogleDriveStorage

        return GoogleDriveStorage()
    raise RuntimeError("Unknown STORAGE_PROVIDER. Supported: supabase, gdrive")
