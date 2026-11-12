import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

password_hasher = PasswordHasher()
DUMMY_PASSWORD_HASH = password_hasher.hash("not-a-real-user-password")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_LIFETIME = timedelta(hours=8)
VERIFICATION_LIFETIME = timedelta(hours=24)
RESET_LIFETIME = timedelta(minutes=30)
INVITATION_LIFETIME = timedelta(days=7)
SESSION_COOKIE_NAME = "maintenance_ai_session"


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY must contain at least 32 bytes.")
    return secret


def validate_jwt_secret() -> None:
    _jwt_secret()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def verify_unknown_user_password(password: str) -> None:
    verify_password(DUMMY_PASSWORD_HASH, password)


def create_access_token(user_id: int, role: str, auth_version: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "role": role,
            "ver": auth_version,
            "iat": now,
            "exp": now + ACCESS_TOKEN_LIFETIME,
        },
        _jwt_secret(),
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_expiration(lifetime: timedelta) -> datetime:
    return datetime.now(timezone.utc) + lifetime
