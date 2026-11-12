from datetime import date, datetime, timezone
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlmodel import Field, SQLModel

EMBEDDING_DIMENSIONS = 384


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LocationType(StrEnum):
    BUILDING = "BUILDING"
    FLOOR = "FLOOR"
    ROOM = "ROOM"
    AREA = "AREA"


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    USER = "USER"


class Organization(SQLModel, table=True):
    __tablename__ = "organization"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=150, index=True)
    description: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Facility(SQLModel, table=True):
    __tablename__ = "facility"

    id: int | None = Field(default=None, primary_key=True)
    organization_id: int = Field(foreign_key="organization.id", index=True)
    name: str = Field(max_length=150)
    description: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_facility_org_name"),
    )


class FunctionalSystem(SQLModel, table=True):
    __tablename__ = "functional_system"

    id: int | None = Field(default=None, primary_key=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    parent_id: int | None = Field(
        default=None,
        foreign_key="functional_system.id",
        index=True,
    )
    name: str = Field(max_length=150)
    description: str | None = None

    __table_args__ = (
        Index(
            "uq_functional_system_root_name",
            "facility_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index(
            "uq_functional_system_child_name",
            "facility_id",
            "parent_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
    )


class PhysicalLocation(SQLModel, table=True):
    __tablename__ = "physical_location"

    id: int | None = Field(default=None, primary_key=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    parent_id: int | None = Field(
        default=None,
        foreign_key="physical_location.id",
        index=True,
    )
    name: str = Field(max_length=150)
    location_type: str = Field(
        sa_column=Column(String(20), nullable=False, index=True)
    )
    description: str | None = None

    __table_args__ = (
        CheckConstraint(
            "location_type IN ('BUILDING', 'FLOOR', 'ROOM', 'AREA')",
            name="ck_physical_location_type",
        ),
        Index(
            "uq_physical_location_root_name",
            "facility_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
        ),
        Index(
            "uq_physical_location_child_name",
            "facility_id",
            "parent_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
    )


class User(SQLModel, table=True):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("role IN ('ADMIN', 'USER')", name="ck_app_user_role"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=150)
    email: str = Field(max_length=320, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    role: str = Field(
        default=UserRole.USER.value,
        sa_column=Column(String(10), nullable=False, index=True),
    )
    is_verified: bool = Field(default=False)
    is_approved: bool = Field(default=False)
    is_invited: bool = Field(default=False)
    is_active: bool = Field(default=True)
    auth_version: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: datetime | None = Field(default=None, index=True)


class PendingRegistration(SQLModel, table=True):
    __tablename__ = "pending_registration"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=150)
    email: str = Field(max_length=320, unique=True, index=True)
    password_hash: str = Field(max_length=255)
    verification_token_hash: str = Field(max_length=64, unique=True, index=True)
    expires_at: datetime = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now)


class PasswordResetToken(SQLModel, table=True):
    __tablename__ = "password_reset_token"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    token_hash: str = Field(max_length=64, unique=True, index=True)
    expires_at: datetime = Field(index=True)
    used_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class AdminInvitation(SQLModel, table=True):
    __tablename__ = "admin_invitation"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(max_length=320, index=True)
    token_hash: str = Field(max_length=64, unique=True, index=True)
    invited_by_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
    )
    expires_at: datetime = Field(index=True)
    accepted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class UserInvitation(SQLModel, table=True):
    __tablename__ = "user_invitation"

    id: int | None = Field(default=None, primary_key=True)
    email: str | None = Field(default=None, max_length=320, index=True)
    token_hash: str = Field(max_length=64, unique=True, index=True)
    invited_by_user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
    )
    failed_attempts: int = Field(default=0)
    expires_at: datetime = Field(index=True)
    accepted_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Machine(SQLModel, table=True):
    __tablename__ = "machine"

    id: int | None = Field(default=None, primary_key=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    functional_system_id: int | None = Field(
        default=None,
        foreign_key="functional_system.id",
        index=True,
    )
    physical_location_id: int | None = Field(
        default=None,
        foreign_key="physical_location.id",
        index=True,
    )
    machine_name: str = Field(max_length=150, index=True)
    machine_code: str = Field(max_length=80)
    description: str | None = None
    status: str = Field(default="ACTIVE", max_length=30, index=True)
    is_deleted: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "facility_id",
            "machine_code",
            name="uq_machine_facility_code",
        ),
    )


class MaintenanceLog(SQLModel, table=True):
    __tablename__ = "maintenance_log"

    id: int | None = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id", index=True)
    user_id: int | None = Field(
        default=None,
        foreign_key="app_user.id",
        ondelete="SET NULL",
        index=True,
    )
    record_type: str = Field(max_length=20, index=True)
    description: str = Field(default="")
    symptoms: str | None = None
    repair_actions: str | None = None
    outcome: str | None = None
    status: str = Field(default="OPEN", max_length=20, index=True)
    is_deleted: bool = Field(default=False, index=True)
    recorded_on: date = Field(default_factory=date.today, index=True)
    created_at: datetime = Field(default_factory=utc_now)


class MachineManual(SQLModel, table=True):
    __tablename__ = "machine_manual"

    id: int | None = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id", index=True)
    document_id: str = Field(max_length=36, unique=True, index=True)
    filename: str = Field(max_length=255)
    file_path: str = Field(max_length=1024)
    uploaded_at: datetime = Field(default_factory=utc_now)


class SearchableChunk(SQLModel, table=True):
    __tablename__ = "searchable_chunk"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "chunk_index",
            name="uq_searchable_chunk_source",
        ),
        Index(
            "ix_searchable_chunk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_searchable_chunk_search_vector_gin",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    facility_id: int = Field(foreign_key="facility.id", index=True)
    machine_id: int = Field(foreign_key="machine.id", index=True)
    source_type: str = Field(max_length=30, index=True)
    source_id: str = Field(max_length=100, index=True)
    chunk_index: int = 0
    manual_id: int | None = Field(
        default=None,
        foreign_key="machine_manual.id",
        ondelete="CASCADE",
    )
    maintenance_log_id: int | None = Field(
        default=None,
        foreign_key="maintenance_log.id",
        ondelete="CASCADE",
    )
    document_id: str | None = Field(default=None, max_length=36, index=True)
    filename: str | None = Field(default=None, max_length=255)
    page_number: int | None = None
    text: str
    search_vector: str = Field(
        sa_column=Column(
            TSVECTOR,
            Computed("to_tsvector('english', text)", persisted=True),
            nullable=False,
        )
    )
    embedding: list[float] | None = Field(
        default=None,
        sa_column=Column(Vector(EMBEDDING_DIMENSIONS), nullable=True),
    )
