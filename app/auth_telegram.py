from __future__ import annotations

import hashlib
import hmac
import time

from app.config import settings


def verify_telegram_login(payload: dict) -> bool:
    bot_token = settings.telegram_bot_token
    if not bot_token:
        return False

    received_hash = payload.get("hash")
    auth_date = int(payload.get("auth_date", 0))
    if not received_hash or not auth_date:
        return False

    now = int(time.time())
    if now - auth_date > settings.telegram_auth_max_age:
        return False

    data_check_items: list[str] = []
    for key in sorted(payload.keys()):
        if key == "hash":
            continue
        value = payload[key]
        if value is None:
            continue
        data_check_items.append(f"{key}={value}")
    data_check_string = "\n".join(data_check_items)

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    computed_hash = hmac.new(
        secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_hash, str(received_hash))
