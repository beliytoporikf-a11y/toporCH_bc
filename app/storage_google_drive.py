from __future__ import annotations

import io
from typing import BinaryIO

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.config import settings


class GoogleDriveStorage:
    def __init__(self):
        if not settings.google_drive_enabled:
            raise RuntimeError("Google Drive storage is disabled")
        if not settings.google_drive_service_account_json:
            raise RuntimeError("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is empty")
        if not settings.google_drive_folder_id:
            raise RuntimeError("GOOGLE_DRIVE_FOLDER_ID is empty")

        creds = service_account.Credentials.from_service_account_file(
            settings.google_drive_service_account_json,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.folder_id = settings.google_drive_folder_id

    def upload_file(
        self,
        filename: str,
        stream: BinaryIO,
        content_type: str = "application/octet-stream",
        user_id: int | None = None,
    ) -> str:
        metadata = {"name": filename, "parents": [self.folder_id]}
        media = MediaIoBaseUpload(stream, mimetype=content_type, resumable=False)
        created = (
            self.service.files()
            .create(body=metadata, media_body=media, fields="id")
            .execute()
        )
        return created["id"]

    def download_file(self, file_id: str) -> bytes:
        request = self.service.files().get_media(fileId=file_id)
        output = io.BytesIO()
        downloader = MediaIoBaseDownload(output, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        output.seek(0)
        return output.read()


def get_storage() -> GoogleDriveStorage:
    return GoogleDriveStorage()
