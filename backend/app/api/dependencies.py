from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlmodel import Session

from backend.app.db.connection import get_session
from backend.app.models.maintenance import User, UserRole
from backend.app.services.auth_security import (
    SESSION_COOKIE_NAME,
    decode_access_token,
)


def get_current_user(
    access_token: Annotated[
        str | None,
        Cookie(alias=SESSION_COOKIE_NAME),
    ] = None,
    session: Session = Depends(get_session),
) -> User:
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required.",
        )
    try:
        payload = decode_access_token(access_token)
        user_id = int(payload["sub"])
        auth_version = int(payload["ver"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is invalid or has expired.",
        ) from error

    user = session.get(User, user_id)
    if (
        user is None
        or user.deleted_at is not None
        or not user.is_active
        or user.auth_version != auth_version
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is no longer active.",
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email before accessing the application.",
        )
    if payload.get("role") != user.role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is invalid.",
        )
    return user


def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access is required.",
        )
    return user


def require_user(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != UserRole.USER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User access is required.",
        )
    return user


def require_approved_user(
    user: User = Depends(get_current_user),
) -> User:
    if (
        user.role != UserRole.ADMIN.value
        and not user.is_approved
        and not user.is_invited
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Administrator approval or a valid user invitation is required "
                "to use AI assistance or register machines."
            ),
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
ApprovedUser = Annotated[User, Depends(require_approved_user)]
AdminUser = Annotated[User, Depends(require_admin)]
RegularUser = Annotated[User, Depends(require_user)]
