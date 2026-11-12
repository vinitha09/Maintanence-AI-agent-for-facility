from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, EmailStr, Field, field_validator

from backend.app.schemas.facility import APIModel


class UserRegisterRequest(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank.")
        return normalized


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class AdminLoginRequest(LoginRequest):
    role: Literal["ADMIN"] = "ADMIN"


class UserRead(APIModel):
    id: int
    name: str
    email: EmailStr
    role: Literal["ADMIN", "USER"]
    is_verified: bool
    is_approved: bool
    is_invited: bool = False
    is_active: bool
    created_at: datetime


class AuthResponse(APIModel):
    user: UserRead


class TokenRequest(APIModel):
    token: str = Field(min_length=20, max_length=512)


class PasswordResetRequest(APIModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class PasswordResetConfirm(TokenRequest):
    password: str = Field(min_length=8, max_length=128)


class AdminInvitationRequest(APIModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserInvitationRequest(APIModel):
    email: EmailStr | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None


class AdminInvitationAccept(TokenRequest):
    name: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank.")
        return normalized


class UserInvitationAccept(TokenRequest):
    email: EmailStr
    token: str = Field(min_length=7, max_length=7)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("token")
    @classmethod
    def normalize_invitation_code(cls, value: str) -> str:
        normalized = value.strip()
        return normalized.upper() if len(normalized) == 7 else normalized

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank.")
        return normalized


class UserStatusUpdate(APIModel):
    is_active: bool
