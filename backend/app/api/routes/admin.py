import logging
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from backend.app.api.dependencies import AdminUser
from backend.app.db.connection import get_session
from backend.app.models.maintenance import (
    AdminInvitation,
    User,
    UserInvitation,
    UserRole,
    utc_now,
)
from backend.app.schemas.auth import (
    AdminInvitationRequest,
    UserRead,
    UserInvitationRequest,
    UserStatusUpdate,
)
from backend.app.services.auth_security import (
    INVITATION_LIFETIME,
    generate_opaque_token,
    hash_opaque_token,
    token_expiration,
)
from backend.app.services.email import (
    EmailConfigurationError,
    EmailDeliveryError,
    send_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["administrator"])
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")


@router.get("/users", response_model=list[UserRead])
def list_users(
    _: AdminUser,
    session: Session = Depends(get_session),
    role: UserRole | None = None,
    is_approved: bool | None = None,
):
    statement = select(User).where(User.deleted_at.is_(None))
    if role is not None:
        statement = statement.where(User.role == role.value)
    if is_approved is not None:
        statement = statement.where(User.is_approved == is_approved)
    return session.exec(statement.order_by(User.created_at.desc())).all()


@router.post("/users/{user_id}/approve", response_model=UserRead)
def approve_user(
    user_id: int,
    _: AdminUser,
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role != UserRole.USER.value or not user.is_verified:
        raise HTTPException(status_code=409, detail="Only verified user registrations can be approved.")
    user.is_approved = True
    user.updated_at = utc_now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/users/{user_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_user(
    user_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot reject your own account.")
    user.is_active = False
    user.auth_version += 1
    user.deleted_at = utc_now()
    user.updated_at = utc_now()
    session.add(user)
    session.commit()


@router.patch("/users/{user_id}/status", response_model=UserRead)
def update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id and not data.is_active:
        raise HTTPException(status_code=400, detail="You cannot suspend your own account.")
    if user.is_active != data.is_active:
        user.is_active = data.is_active
        user.auth_version += 1
        user.updated_at = utc_now()
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    user = session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    user.is_active = False
    user.is_approved = False
    user.auth_version += 1
    user.deleted_at = utc_now()
    user.updated_at = utc_now()
    session.add(user)
    session.commit()


@router.post("/invitations", status_code=status.HTTP_202_ACCEPTED)
def invite_admin(
    data: AdminInvitationRequest,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    user_exists = session.exec(
        select(User.id).where(User.email == data.email)
    ).first()
    if user_exists is not None:
        raise HTTPException(status_code=409, detail="An account already uses this email.")

    invitations = session.exec(
        select(AdminInvitation).where(
            AdminInvitation.email == data.email,
            AdminInvitation.accepted_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    if any(
        (
            invitation.expires_at.replace(tzinfo=timezone.utc)
            if invitation.expires_at.tzinfo is None
            else invitation.expires_at
        )
        > now
        for invitation in invitations
    ):
        raise HTTPException(status_code=409, detail="A valid invitation already exists for this email.")

    raw_token = generate_opaque_token()
    invitation = AdminInvitation(
        email=data.email,
        token_hash=hash_opaque_token(raw_token),
        invited_by_user_id=admin.id,
        expires_at=token_expiration(INVITATION_LIFETIME),
    )
    session.add(invitation)
    session.commit()

    try:
        send_email(
            data.email,
            "Maintenance AI administrator invitation",
            "An administrator invited you to create an administrator account:\n"
            f"{FRONTEND_URL}/?auth=admin-invitation&token={raw_token}\n\n"
            "This invitation expires in 7 days.",
        )
    except (EmailConfigurationError, EmailDeliveryError) as error:
        session.delete(invitation)
        session.commit()
        logger.exception("Could not send administrator invitation.")
        raise HTTPException(
            status_code=503,
            detail="Invitation email could not be sent. Check the email configuration and try again.",
        ) from error
    return {"message": "Administrator invitation sent."}


@router.post("/user-invitations", status_code=status.HTTP_202_ACCEPTED)
def invite_user(
    data: UserInvitationRequest,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    if data.email is not None:
        existing_user = session.exec(
            select(User).where(User.email == data.email)
        ).first()
        if existing_user is not None and (
            existing_user.deleted_at is not None
            or existing_user.role != UserRole.USER.value
            or not existing_user.is_active
            or existing_user.is_approved
            or existing_user.is_invited
        ):
            raise HTTPException(
                status_code=409,
                detail="This account cannot be invited or already has full access.",
            )

        invitations = session.exec(
            select(UserInvitation).where(
                UserInvitation.email == data.email,
                UserInvitation.accepted_at.is_(None),
            )
        ).all()
        now = datetime.now(timezone.utc)
        if any(
            (
                invitation.expires_at.replace(tzinfo=timezone.utc)
                if invitation.expires_at.tzinfo is None
                else invitation.expires_at
            )
            > now
            for invitation in invitations
        ):
            raise HTTPException(status_code=409, detail="A valid invitation already exists for this email.")

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    digits = "23456789"
    invitation_code = "".join(secrets.choice(alphabet) for _ in range(4))
    invitation_code += "".join(secrets.choice(digits) for _ in range(3))
    invitation = UserInvitation(
        email=data.email,
        token_hash=hash_opaque_token(invitation_code),
        invited_by_user_id=admin.id,
        expires_at=token_expiration(INVITATION_LIFETIME),
    )
    session.add(invitation)
    session.commit()

    if data.email is None:
        return {
            "message": "Shared recruiter invitation code generated.",
            "code": invitation_code,
            "expires_in_days": INVITATION_LIFETIME.days,
        }

    try:
        send_email(
            data.email,
            "Maintenance AI user invitation",
            "An administrator invited you to create a Maintenance AI user account:\n"
            f"{FRONTEND_URL}/?auth=user-invitation\n\n"
            f"Invitation code: {invitation_code}\n"
            f"Enter the invited email address and this code on the invitation page.\n\n"
            "Accepting this invitation grants access without separate administrator approval. "
            "This code is for the invited email address, expires in 7 days, and can be used once.",
        )
    except (EmailConfigurationError, EmailDeliveryError) as error:
        session.delete(invitation)
        session.commit()
        logger.exception("Could not send user invitation.")
        raise HTTPException(
            status_code=503,
            detail="Invitation email could not be sent. Check the email configuration and try again.",
        ) from error
    return {"message": "User invitation sent."}
