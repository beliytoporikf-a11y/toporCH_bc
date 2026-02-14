from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_telegram import verify_telegram_login
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import MeResponse, TelegramLoginPayload, TokenResponse
from app.security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=TokenResponse)
def telegram_login(payload: TelegramLoginPayload, db: Session = Depends(get_db)):
    payload_dict = payload.model_dump()
    if not verify_telegram_login(payload_dict):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Telegram auth failed")

    user = db.query(User).filter(User.telegram_id == payload.id).first()
    if user is None:
        user = User(
            telegram_id=payload.id,
            username=payload.username,
            first_name=payload.first_name,
            last_name=payload.last_name,
            photo_url=payload.photo_url,
            is_admin=payload.id in settings.telegram_admin_ids,
        )
        db.add(user)
    else:
        user.username = payload.username
        user.first_name = payload.first_name
        user.last_name = payload.last_name
        user.photo_url = payload.photo_url
        if payload.id in settings.telegram_admin_ids:
            user.is_admin = True

    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)):
    return MeResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_admin=bool(user.is_admin),
    )


@router.post("/admin/assign/{target_telegram_id}")
def assign_admin(
    target_telegram_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    target = db.query(User).filter(User.telegram_id == target_telegram_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    target.is_admin = True
    db.commit()
    return {"ok": True, "telegram_id": target_telegram_id, "is_admin": True}


@router.post("/telegram/phone/start")
def telegram_phone_login_not_supported():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Phone/QR login for Telegram account requires MTProto (api_id/api_hash). "
            "Bot token is not enough."
        ),
    )


@router.get("/telegram/qr/start")
def telegram_qr_login_not_supported():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "QR login for Telegram account requires MTProto (api_id/api_hash). "
            "Bot token is not enough."
        ),
    )
