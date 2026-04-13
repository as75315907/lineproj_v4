from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import settings

admin_basic_auth = HTTPBasic(auto_error=False)


def verify_line_signature(body: bytes, signature: str) -> bool:
    if not settings.line_channel_secret:
        return settings.test_mode
    if not signature:
        return False
    digest = hmac.new(settings.line_channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def require_admin_auth(credentials: HTTPBasicCredentials | None = Depends(admin_basic_auth)) -> None:
    if not settings.admin_auth_enabled:
        return
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin auth required",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = secrets.compare_digest(credentials.username, settings.admin_username)
    password_ok = secrets.compare_digest(credentials.password, settings.admin_password)
    if username_ok and password_ok:
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid admin credentials",
        headers={"WWW-Authenticate": "Basic"},
    )
