from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import quote
from uuid import uuid4

import requests

from app.config import settings


class SupabaseStorage:
    def __init__(self):
        if not settings.supabase_url:
            raise RuntimeError("SUPABASE_URL is empty")
        if not settings.supabase_bucket:
            raise RuntimeError("SUPABASE_BUCKET is empty")

        self.base_url = settings.supabase_url.rstrip("/")
        self.bucket = settings.supabase_bucket
        self.s3_client = None

        # Option A: S3-compatible API (access key + secret)
        if settings.supabase_s3_access_key_id and settings.supabase_s3_secret_access_key:
            try:
                import boto3  # type: ignore
            except ImportError as exc:
                raise RuntimeError("boto3 is required for SUPABASE_S3_ACCESS_KEY_ID mode") from exc
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=f"{self.base_url}/storage/v1/s3",
                aws_access_key_id=settings.supabase_s3_access_key_id,
                aws_secret_access_key=settings.supabase_s3_secret_access_key,
                region_name=settings.supabase_s3_region or "us-east-1",
            )
            self.headers = {}
            return

        # Option B: REST API (service_role preferred, publishable as fallback)
        api_key = settings.supabase_service_role_key or settings.supabase_publishable_key
        if not api_key:
            raise RuntimeError(
                "Set SUPABASE_SERVICE_ROLE_KEY (recommended) or SUPABASE_PUBLISHABLE_KEY"
            )
        self.headers = {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
        }

    def _object_path(self, filename: str, user_id: int | None = None) -> str:
        safe_name = os.path.basename(filename or "track.bin")
        stamp = datetime.utcnow().strftime("%Y%m%d")
        prefix = f"user_{user_id}" if user_id else "shared"
        return f"{prefix}/{stamp}/{uuid4().hex}_{safe_name}"

    def upload_file(
        self,
        filename: str,
        stream,
        content_type: str = "application/octet-stream",
        user_id: int | None = None,
    ) -> str:
        object_path = self._object_path(filename=filename, user_id=user_id)

        if self.s3_client is not None:
            self.s3_client.upload_fileobj(
                Fileobj=stream,
                Bucket=self.bucket,
                Key=object_path,
                ExtraArgs={"ContentType": content_type},
            )
            return object_path

        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{quote(object_path, safe='/')}"
        data = stream.read()
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }
        response = requests.post(url, headers=headers, data=data, timeout=120)
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase upload failed: {response.status_code} {response.text}")
        return object_path

    def download_file(self, object_path: str) -> bytes:
        if self.s3_client is not None:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=object_path)
            return response["Body"].read()

        url = f"{self.base_url}/storage/v1/object/{self.bucket}/{quote(object_path, safe='/')}"
        response = requests.get(url, headers=self.headers, timeout=120)
        if response.status_code >= 300:
            raise RuntimeError(f"Supabase download failed: {response.status_code} {response.text}")
        return response.content
