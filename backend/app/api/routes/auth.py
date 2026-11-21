import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.dependencies import CurrentUser
from backend.app.db.connection import get_session
from backend.app.models.maintenance import (
    AdminInvitation,
    PasswordResetToken,
    PendingRegistration,
    User,
    UserInvitation,
    UserRole,
    utc_now,
)
from backend.app.schemas.auth import (
    AdminInvitationAccept,
    AuthResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenRequest,
    UserInvitationAccept,
    UserRead,
    UserRegisterRequest,
)
from backend.app.services.auth_security import (
    ACCESS_TOKEN_LIFETIME,
    INVITATION_LIFETIME,
    RESET_LIFETIME,
    SESSION_COOKIE_NAME,
    VERIFICATION_LIFETIME,
    create_access_token,
    decode_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    token_expiration,
    verify_password,
    verify_unknown_user_password,
)
from backend.app.services.email import (
    EmailConfigurationError,
    EmailDeliveryError,
    send_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
COOKIE_NAME = SESSION_COOKIE_NAME
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://maintanence-ai-agent-for-facility.pages.dev").rstrip("/")


def _set_session_cookie(response: Response, user: User) -> None:
    if user.id is None:
        raise RuntimeError("Cannot create a session for a user without an ID.")
    token = create_access_token(user.id, user.role, user.auth_version)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        path="/",
    )


def _frontend_link(page: str, token: str) -> str:
    return f"{FRONTEND_URL}/?{urlencode({'auth': page, 'token': token})}"


def _is_expired(expiration: datetime) -> bool:
    if expiration.tzinfo is None:
        expiration = expiration.replace(tzinfo=timezone.utc)
    return expiration <= datetime.now(timezone.utc)


def _login(
    data: LoginRequest,
    expected_role: UserRole,
    response: Response,
    session: Session,
) -> AuthResponse:
    user = session.exec(
        select(User).where(User.email == data.email, User.deleted_at.is_(None))
    ).first()
    if user is None:
        verify_unknown_user_password(data.password)
        password_matches = False
    else:
        password_matches = verify_password(user.password_hash, data.password)
    if not password_matches or user is None or user.role != expected_role.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is suspended or inactive.",
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verify your email before signing in.",
        )
    _set_session_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register_user(
    data: UserRegisterRequest,
    session: Session = Depends(get_session),
):
    existing_user = session.exec(
        select(User.id).where(User.email == data.email)
    ).first()
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="This email is already registered.")
    existing_pending = session.exec(
        select(PendingRegistration).where(PendingRegistration.email == data.email)
    ).first()
    if existing_pending is not None:
        session.delete(existing_pending)
        session.flush()

    raw_token = generate_opaque_token()
    pending = PendingRegistration(
        name=data.name.strip(),
        email=data.email,
        password_hash=hash_password(data.password),
        verification_token_hash=hash_opaque_token(raw_token),
        expires_at=token_expiration(VERIFICATION_LIFETIME),
    )
    session.add(pending)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This email is already registered.") from error

    try:
        send_email(
            data.email,
            "Verify your Maintenance AI account",
            f"Hello {data.name},\n\nVerify your email to submit your account for administrator approval:\n"
            f"{_frontend_link('verify', raw_token)}\n\nThis link expires in 24 hours.",
        )
    except (EmailConfigurationError, EmailDeliveryError) as error:
        session.delete(pending)
        session.commit()
        logger.exception("Could not send account verification email.")
        raise HTTPException(
            status_code=503,
            detail="Registration email could not be sent. Check the email configuration and try again.",
        ) from error
    return {"message": "Check your email to verify your account."}


@router.post("/verify-email", response_model=UserRead)
def verify_email(
    data: TokenRequest,
    session: Session = Depends(get_session),
):
    pending = session.exec(
        select(PendingRegistration).where(
            PendingRegistration.verification_token_hash
            == hash_opaque_token(data.token)
        ).with_for_update()
    ).first()
    if pending is None or _is_expired(pending.expires_at):
        raise HTTPException(status_code=400, detail="Verification link is invalid or expired.")

    user = User(
        name=pending.name,
        email=pending.email,
        password_hash=pending.password_hash,
        role=UserRole.USER.value,
        is_verified=True,
        is_approved=False,
        is_active=True,
    )
    session.add(user)
    session.delete(pending)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This email is already registered.") from error
    session.refresh(user)
    return user


@router.post("/user/login", response_model=AuthResponse)
def user_login(
    data: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
):
    return _login(data, UserRole.USER, response, session)


@router.post("/admin/login", response_model=AuthResponse)
def admin_login(
    data: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
):
    return _login(data, UserRole.ADMIN, response, session)


@router.get("/me", response_model=UserRead)
def get_session_user(user: CurrentUser):
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    request: Request,
    session: Session = Depends(get_session),
):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            user_id = int(decode_access_token(token)["sub"])
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            user_id = None
        if user_id is not None:
            user = session.get(User, user_id)
            if user is not None:
                user.auth_version += 1
                user.updated_at = utc_now()
                session.add(user)
                session.commit()
    _clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/forgot-password")
def forgot_password(
    data: PasswordResetRequest,
    session: Session = Depends(get_session),
):
    user = session.exec(
        select(User).where(
            User.email == data.email,
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    ).first()
    if user is not None:
        raw_token = generate_opaque_token()
        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_opaque_token(raw_token),
            expires_at=token_expiration(RESET_LIFETIME),
        )
        session.add(reset)
        session.commit()
        try:
            send_email(
                user.email,
                "Reset your Maintenance AI password",
                f"Reset your password using this link:\n{_frontend_link('reset', raw_token)}\n\n"
                "This link expires in 30 minutes. If you did not request a reset, ignore this email.",
            )
        except (EmailConfigurationError, EmailDeliveryError) as error:
            logger.exception("Could not send password reset email.")
            raise HTTPException(
                status_code=503,
                detail="Password reset email could not be sent. Check the email configuration.",
            ) from error
    return {"message": "If that account exists, password reset instructions have been sent."}


@router.post("/reset-password")
def reset_password(
    data: PasswordResetConfirm,
    response: Response,
    session: Session = Depends(get_session),
):
    reset = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_opaque_token(data.token),
            PasswordResetToken.used_at.is_(None),
        ).with_for_update()
    ).first()
    if reset is None or _is_expired(reset.expires_at):
        raise HTTPException(status_code=400, detail="Password reset link is invalid or expired.")
    user = session.get(User, reset.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Password reset link is invalid or expired.")
    user.password_hash = hash_password(data.password)
    user.auth_version += 1
    user.updated_at = utc_now()
    reset.used_at = utc_now()
    session.add(user)
    session.add(reset)
    for other_reset in session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all():
        other_reset.used_at = utc_now()
        session.add(other_reset)
    session.commit()
    _clear_session_cookie(response)
    return {"message": "Password reset successfully. Sign in with your new password."}


@router.post("/admin-invitations/accept", response_model=AuthResponse)
def accept_admin_invitation(
    data: AdminInvitationAccept,
    response: Response,
    session: Session = Depends(get_session),
):
    invitation = session.exec(
        select(AdminInvitation).where(
            AdminInvitation.token_hash == hash_opaque_token(data.token),
            AdminInvitation.accepted_at.is_(None),
        ).with_for_update()
    ).first()
    if invitation is None or _is_expired(invitation.expires_at):
        raise HTTPException(status_code=400, detail="Administrator invitation is invalid or expired.")
    if session.exec(select(User.id).where(User.email == invitation.email)).first():
        raise HTTPException(status_code=409, detail="This email is already registered.")
    pending_registration = session.exec(
        select(PendingRegistration).where(
            PendingRegistration.email == invitation.email
        )
    ).first()
    user = User(
        name=data.name.strip(),
        email=invitation.email,
        password_hash=hash_password(data.password),
        role=UserRole.ADMIN.value,
        is_verified=True,
        is_approved=True,
        is_active=True,
    )
    invitation.accepted_at = utc_now()
    session.add(user)
    session.add(invitation)
    if pending_registration is not None:
        session.delete(pending_registration)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This email is already registered.") from error
    session.refresh(user)
    _set_session_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))


@router.post("/user-invitations/accept", response_model=AuthResponse)
def accept_user_invitation(
    data: UserInvitationAccept,
    response: Response,
    session: Session = Depends(get_session),
):
    invitation = session.exec(
        select(UserInvitation)
        .where(
            UserInvitation.token_hash == hash_opaque_token(data.token),
            UserInvitation.accepted_at.is_(None),
        )
        .with_for_update()
    ).first()
    if (
        invitation is None
        or _is_expired(invitation.expires_at)
        or (
            invitation.email is not None
            and invitation.email != data.email
        )
    ):
        raise HTTPException(status_code=400, detail="User invitation is invalid or expired.")
    user = session.exec(
        select(User).where(User.email == data.email).with_for_update()
    ).first()
    pending_registration = session.exec(
        select(PendingRegistration).where(
            PendingRegistration.email == data.email
        )
    ).first()
    if user is not None:
        if (
            user.deleted_at is not None
            or user.role != UserRole.USER.value
            or not user.is_active
        ):
            raise HTTPException(
                status_code=409,
                detail="This account cannot accept the invitation.",
            )
        if not verify_password(user.password_hash, data.password):
            raise HTTPException(
                status_code=401,
                detail="The email or password is incorrect.",
            )
        user.is_verified = True
        user.is_invited = True
        user.updated_at = utc_now()
    else:
        if data.name is None:
            raise HTTPException(
                status_code=400,
                detail="Enter your name to create a new user account.",
            )
        user = User(
            name=data.name.strip(),
            email=data.email,
            password_hash=hash_password(data.password),
            role=UserRole.USER.value,
            is_verified=True,
            is_approved=False,
            is_invited=True,
            is_active=True,
        )
    if invitation.email is not None:
        invitation.accepted_at = utc_now()
    session.add(user)
    session.add(invitation)
    if pending_registration is not None:
        session.delete(pending_registration)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail="This email is already registered.") from error
    session.refresh(user)
    _set_session_cookie(response, user)
    return AuthResponse(user=UserRead.model_validate(user))
