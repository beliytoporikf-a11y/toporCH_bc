from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LibraryTrack, User
from app.schemas import TrackCountersUpdate, TrackCreate, TrackOut
from app.security import get_current_user
from app.storage_factory import get_storage

router = APIRouter(prefix="/me/library", tags=["library"])


@router.get("/tracks", response_model=list[TrackOut])
def get_tracks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(LibraryTrack)
        .filter(LibraryTrack.user_id == user.id)
        .order_by(LibraryTrack.id.desc())
        .all()
    )
    return [
        TrackOut(
            id=row.id,
            path=row.path,
            filename=row.filename,
            title=row.title,
            artist=row.artist,
            album=row.album,
            duration_ms=row.duration_ms,
            remote_file_key=row.remote_file_key,
            cover_url=row.cover_url,
            play_count=row.play_count,
            skip_count=row.skip_count,
        )
        for row in rows
    ]


@router.post("/tracks", response_model=TrackOut)
def add_track(payload: TrackCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = LibraryTrack(
        user_id=user.id,
        path=payload.path,
        filename=payload.filename,
        title=payload.title,
        artist=payload.artist,
        album=payload.album,
        duration_ms=payload.duration_ms,
        remote_file_key=payload.remote_file_key,
        cover_url=payload.cover_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return TrackOut(
        id=row.id,
        path=row.path,
        filename=row.filename,
        title=row.title,
        artist=row.artist,
        album=row.album,
        duration_ms=row.duration_ms,
        remote_file_key=row.remote_file_key,
        cover_url=row.cover_url,
        play_count=row.play_count,
        skip_count=row.skip_count,
    )


@router.patch("/tracks/{track_id}/counters", response_model=TrackOut)
def patch_track_counters(
    track_id: int,
    payload: TrackCountersUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(LibraryTrack)
        .filter(LibraryTrack.id == track_id, LibraryTrack.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")

    row.play_count = max(0, row.play_count + payload.play_count_delta)
    row.skip_count = max(0, row.skip_count + payload.skip_count_delta)
    db.commit()
    db.refresh(row)

    return TrackOut(
        id=row.id,
        path=row.path,
        filename=row.filename,
        title=row.title,
        artist=row.artist,
        album=row.album,
        duration_ms=row.duration_ms,
        remote_file_key=row.remote_file_key,
        cover_url=row.cover_url,
        play_count=row.play_count,
        skip_count=row.skip_count,
    )


@router.post("/tracks/upload", response_model=TrackOut)
async def upload_track_to_cloud(
    file: UploadFile = File(...),
    title: str | None = None,
    artist: str | None = None,
    album: str | None = None,
    duration_ms: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        storage = get_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    filename = file.filename or "track.bin"
    content_type = file.content_type or "application/octet-stream"
    file_id = storage.upload_file(
        filename=filename,
        stream=file.file,
        content_type=content_type,
        user_id=user.id,
    )

    row = LibraryTrack(
        user_id=user.id,
        filename=filename,
        title=title or filename,
        artist=artist,
        album=album,
        duration_ms=duration_ms,
        remote_file_key=file_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return TrackOut(
        id=row.id,
        path=row.path,
        filename=row.filename,
        title=row.title,
        artist=row.artist,
        album=row.album,
        duration_ms=row.duration_ms,
        remote_file_key=row.remote_file_key,
        cover_url=row.cover_url,
        play_count=row.play_count,
        skip_count=row.skip_count,
    )


@router.get("/tracks/{track_id}/download")
def download_track_from_cloud(
    track_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(LibraryTrack)
        .filter(LibraryTrack.id == track_id, LibraryTrack.user_id == user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Track not found")
    if not row.remote_file_key:
        raise HTTPException(status_code=400, detail="Track has no remote_file_key")

    try:
        storage = get_storage()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    data = storage.download_file(row.remote_file_key)
    filename = row.filename or f"track_{row.id}.bin"
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
