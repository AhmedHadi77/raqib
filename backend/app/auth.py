"""JWT authentication + role-based access control (admin > operator > viewer)."""
from __future__ import annotations

import hmac
import time

import jwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

ROLE_LEVEL = {"viewer": 0, "operator": 1, "admin": 2}
bearer = HTTPBearer(auto_error=False)
USER_STORE = None   # set by main.py at start-up (accounts live in SQLite after the first run)


def authenticate(username: str, password: str) -> str | None:
    """Returns the role if the credentials are valid."""
    if USER_STORE is not None:
        u = USER_STORE.get_user(username)
        if u and not u["disabled"] and USER_STORE.check_password(password, u["pw"]):
            return u["role"]
        return None
    entry = get_settings().user_table.get(username)
    if entry and hmac.compare_digest(entry[0].encode(), password.encode()):
        return entry[1]
    return None


def create_token(username: str, role: str) -> tuple[str, int]:
    s = get_settings()
    exp = s.jwt_expire_hours * 3600
    now = int(time.time())
    token = jwt.encode({"sub": username, "role": role, "iat": now, "exp": now + exp}, s.jwt_secret, algorithm="HS256")
    return token, exp


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token expired") from e
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid token") from e


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                 token: str | None = Query(default=None, include_in_schema=False)) -> dict:
    raw = creds.credentials if creds else token   # ?token= is allowed for <Image> and WebSocket URLs
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    return decode_token(raw)


def require_role(min_role: str):
    def dep(user: dict = Depends(current_user)) -> dict:
        if ROLE_LEVEL.get(user.get("role"), -1) < ROLE_LEVEL[min_role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires role '{min_role}'")
        return user

    return dep
