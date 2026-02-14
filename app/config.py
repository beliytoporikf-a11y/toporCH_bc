from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _parse_int_set(raw: str) -> frozenset[int]:
    result: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            continue
    return frozenset(result)


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "toporCH Backend")
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_debug: bool = os.getenv("APP_DEBUG", "true").lower() == "true"

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./toporch_backend.db")

    jwt_secret: str = os.getenv("JWT_SECRET", "change_me_super_secret")
    jwt_alg: str = os.getenv("JWT_ALG", "HS256")
    jwt_expire_seconds: int = int(os.getenv("JWT_EXPIRE_SECONDS", "2592000"))

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_auth_max_age: int = int(os.getenv("TELEGRAM_AUTH_MAX_AGE", "86400"))
    telegram_admin_ids: frozenset[int] = _parse_int_set(os.getenv("TELEGRAM_ADMIN_IDS", ""))
    telegram_api_id: int = int(os.getenv("TELEGRAM_API_ID", "0") or "0")
    telegram_api_hash: str = os.getenv("TELEGRAM_API_HASH", "")

    storage_provider: str = os.getenv("STORAGE_PROVIDER", "supabase").lower()
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_publishable_key: str = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    supabase_s3_access_key_id: str = os.getenv("SUPABASE_S3_ACCESS_KEY_ID", "")
    supabase_s3_secret_access_key: str = os.getenv("SUPABASE_S3_SECRET_ACCESS_KEY", "")
    supabase_s3_region: str = os.getenv("SUPABASE_S3_REGION", "us-east-1")
    supabase_bucket: str = os.getenv("SUPABASE_BUCKET", "music")

    google_drive_enabled: bool = os.getenv("GOOGLE_DRIVE_ENABLED", "false").lower() == "true"
    google_drive_service_account_json: str = os.getenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON", "")
    google_drive_folder_id: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")


settings = Settings()
