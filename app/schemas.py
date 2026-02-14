from __future__ import annotations

from pydantic import BaseModel


class TelegramLoginPayload(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class AdminBootstrapPayload(BaseModel):
    telegram_id: int
    bot_token: str


class MeResponse(BaseModel):
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    is_admin: bool


class TrackCreate(BaseModel):
    path: str | None = None
    filename: str | None = None
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    duration_ms: int = 0
    remote_file_key: str | None = None
    cover_url: str | None = None


class TrackOut(BaseModel):
    id: int
    path: str | None
    filename: str | None
    title: str | None
    artist: str | None
    album: str | None
    duration_ms: int
    remote_file_key: str | None
    cover_url: str | None
    play_count: int
    skip_count: int


class TrackCountersUpdate(BaseModel):
    play_count_delta: int = 0
    skip_count_delta: int = 0
