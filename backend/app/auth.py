"""
Authentication & authorisation (System Security — Section 3.8, now implemented).

  - Passwords are hashed with PBKDF2-HMAC-SHA256 + per-user salt (stdlib, no weak
    plaintext storage).
  - Login issues a signed JSON Web Token (JWT); protected endpoints require it.
  - Role-based access control: coordinator | researcher | admin.
  - A simple in-memory rate limiter guards the login and compute endpoints.

For production, move SECRET_KEY to an environment secret and serve over HTTPS/TLS.
"""
from __future__ import annotations
import hashlib
import hmac
import os
import time
import secrets
import datetime as dt
from collections import defaultdict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .db import User, get_db

SECRET_KEY = os.environ.get("FLOOD_SECRET", "change-me-in-production-" + "flood-sim-2026")
ALGORITHM = "HS256"
TOKEN_TTL_MIN = 8 * 60

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2$120000${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


# ---------------------------------------------------------------- tokens
def create_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "exp": dt.datetime.utcnow() + dt.timedelta(minutes=TOKEN_TTL_MIN),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    data = decode_token(token)
    user = db.get(User, data.get("sub"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_role(*roles: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if roles and user.role not in roles and user.role != "admin":
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _dep


# ---------------------------------------------------------------- rate limit
_hits: dict[str, list[float]] = defaultdict(list)


def rate_limit(key: str, limit: int = 30, window: float = 60.0):
    now = time.time()
    hits = [t for t in _hits[key] if now - t < window]
    hits.append(now)
    _hits[key] = hits
    if len(hits) > limit:
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
