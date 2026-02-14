from __future__ import annotations

import asyncio
import random
import secrets
import time

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from telethon import TelegramClient
from telethon.errors import PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError
from telethon.sessions import StringSession

from app.auth_telegram import verify_telegram_login
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import (
    AdminBootstrapPayload,
    MeResponse,
    TelegramCodeStartPayload,
    TelegramCodeStartResponse,
    TelegramCodeVerifyPayload,
    TelegramLoginPayload,
    TelegramMtprotoSendCodePayload,
    TelegramMtprotoSendCodeResponse,
    TelegramMtprotoVerifyCodePayload,
    TokenResponse,
)
from app.security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

_LOGIN_CHALLENGES: dict[str, dict] = {}
_MTPROTO_CHALLENGES: dict[str, dict] = {}
_LOGIN_TTL_SECONDS = 300


def _cleanup_challenges():
    now = int(time.time())
    expired_login = [k for k, v in _LOGIN_CHALLENGES.items() if v.get("expires_at", 0) <= now]
    for key in expired_login:
        _LOGIN_CHALLENGES.pop(key, None)
    expired_mt = [k for k, v in _MTPROTO_CHALLENGES.items() if v.get("expires_at", 0) <= now]
    for key in expired_mt:
        _MTPROTO_CHALLENGES.pop(key, None)


def _send_telegram_message(chat_id: int, text: str):
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    response = requests.post(
        url,
        json={"chat_id": int(chat_id), "text": text},
        timeout=20,
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Telegram API error: {response.status_code} {response.text}")


def _upsert_user_by_telegram_id(db: Session, telegram_id: int) -> User:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=None,
            first_name=None,
            last_name=None,
            photo_url=None,
            is_admin=telegram_id in settings.telegram_admin_ids,
        )
        db.add(user)
    else:
        if telegram_id in settings.telegram_admin_ids:
            user.is_admin = True
    db.commit()
    db.refresh(user)
    return user


async def _mtproto_send_code(phone: str) -> tuple[str, str]:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID/TELEGRAM_API_HASH are not configured")
    client = TelegramClient(StringSession(), settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    try:
        result = await client.send_code_request(phone)
        session_str = client.session.save()
        return session_str, result.phone_code_hash
    finally:
        await client.disconnect()


async def _mtproto_verify_code(session_str: str, phone: str, phone_code_hash: str, code: str, password: str | None):
    client = TelegramClient(StringSession(session_str), settings.telegram_api_id, settings.telegram_api_hash)
    await client.connect()
    try:
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                raise RuntimeError("2FA password required")
            await client.sign_in(password=password)
        me = await client.get_me()
        return me
    finally:
        await client.disconnect()


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


@router.post("/telegram/mtproto/send-code", response_model=TelegramMtprotoSendCodeResponse)
def telegram_mtproto_send_code(payload: TelegramMtprotoSendCodePayload):
    _cleanup_challenges()
    phone = (payload.phone or "").strip()
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone is empty")
    try:
        session_str, phone_code_hash = asyncio.run(_mtproto_send_code(phone))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Telegram send-code failed: {e}")

    challenge_id = secrets.token_urlsafe(24)
    _MTPROTO_CHALLENGES[challenge_id] = {
        "phone": phone,
        "session": session_str,
        "phone_code_hash": phone_code_hash,
        "expires_at": int(time.time()) + _LOGIN_TTL_SECONDS,
    }
    return TelegramMtprotoSendCodeResponse(challenge_id=challenge_id, expires_in=_LOGIN_TTL_SECONDS)


@router.post("/telegram/mtproto/verify-code", response_model=TokenResponse)
def telegram_mtproto_verify_code(payload: TelegramMtprotoVerifyCodePayload, db: Session = Depends(get_db)):
    _cleanup_challenges()
    challenge = _MTPROTO_CHALLENGES.get(payload.challenge_id)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login challenge not found or expired")

    try:
        me = asyncio.run(
            _mtproto_verify_code(
                session_str=challenge["session"],
                phone=challenge["phone"],
                phone_code_hash=challenge["phone_code_hash"],
                code=(payload.code or "").strip(),
                password=(payload.password or "").strip() or None,
            )
        )
    except PhoneCodeInvalidError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")
    except PhoneCodeExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Code expired")
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Telegram sign-in failed: {e}")

    _MTPROTO_CHALLENGES.pop(payload.challenge_id, None)

    user = db.query(User).filter(User.telegram_id == int(me.id)).first()
    if user is None:
        user = User(
            telegram_id=int(me.id),
            username=getattr(me, "username", None),
            first_name=getattr(me, "first_name", None),
            last_name=getattr(me, "last_name", None),
            photo_url=None,
            is_admin=int(me.id) in settings.telegram_admin_ids,
        )
        db.add(user)
    else:
        user.username = getattr(me, "username", None)
        user.first_name = getattr(me, "first_name", None)
        user.last_name = getattr(me, "last_name", None)
        if int(me.id) in settings.telegram_admin_ids:
            user.is_admin = True

    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/telegram/code/start", response_model=TelegramCodeStartResponse)
def telegram_code_start(payload: TelegramCodeStartPayload):
    _cleanup_challenges()
    code = f"{random.randint(0, 999999):06d}"
    challenge_id = secrets.token_urlsafe(24)
    expires_at = int(time.time()) + _LOGIN_TTL_SECONDS
    _LOGIN_CHALLENGES[challenge_id] = {
        "telegram_id": int(payload.telegram_id),
        "code": code,
        "expires_at": expires_at,
    }
    text = (
        "toporCH login code:\n"
        f"{code}\n\n"
        "Code is valid for 5 minutes."
    )
    try:
        _send_telegram_message(payload.telegram_id, text)
    except Exception as e:
        _LOGIN_CHALLENGES.pop(challenge_id, None)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return TelegramCodeStartResponse(challenge_id=challenge_id, expires_in=_LOGIN_TTL_SECONDS)


@router.post("/telegram/code/verify", response_model=TokenResponse)
def telegram_code_verify(payload: TelegramCodeVerifyPayload, db: Session = Depends(get_db)):
    _cleanup_challenges()
    challenge = _LOGIN_CHALLENGES.get(payload.challenge_id)
    if not challenge:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login challenge not found or expired")
    if str(payload.code).strip() != str(challenge["code"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid login code")

    telegram_id = int(challenge["telegram_id"])
    _LOGIN_CHALLENGES.pop(payload.challenge_id, None)
    user = _upsert_user_by_telegram_id(db, telegram_id)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/telegram/admin-bootstrap", response_model=TokenResponse)
def telegram_admin_bootstrap(payload: AdminBootstrapPayload, db: Session = Depends(get_db)):
    if payload.bot_token != settings.telegram_bot_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot token")
    if payload.telegram_id not in settings.telegram_admin_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not in admin list")

    user = _upsert_user_by_telegram_id(db, payload.telegram_id)
    user.is_admin = True
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


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
            "Use /auth/telegram/mtproto/send-code and /auth/telegram/mtproto/verify-code."
        ),
    )


@router.get("/telegram/qr/start")
def telegram_qr_login_not_supported():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "QR login is not enabled in this build yet. Use MTProto phone login endpoints."
        ),
    )
