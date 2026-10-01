"""Password hashing, JWT creation/validation and auth dependencies."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request, status

from . import database
from .config import settings


class RedirectToLogin(Exception):
    """Raised by page routes when the visitor is not logged in."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user["id"]),
        "username": user["username"],
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None


def _token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(settings.COOKIE_NAME)


def get_user_from_request(request: Request) -> Optional[dict]:
    token = _token_from_request(request)
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        return None
    user = database.get_user_by_id(user_id)
    if user:
        user["token_exp"] = payload.get("exp")
    return user


def get_optional_user(request: Request) -> Optional[dict]:
    return get_user_from_request(request)


def require_user(request: Request) -> dict:
    """Dependency for JSON API routes -> 401 when not logged in."""
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


def require_user_page(request: Request) -> dict:
    """Dependency for HTML routes -> redirect to /login when not logged in."""
    user = get_user_from_request(request)
    if not user:
        raise RedirectToLogin()
    return user
