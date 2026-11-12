from datetime import date, datetime
from typing import ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class APIUpdateModel(APIModel):
    NON_NULLABLE_FIELDS: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, values):
        if isinstance(values, dict):
            null_fields = [
                field
                for field in cls.NON_NULLABLE_FIELDS
                if field in values and values[field] is None
            ]
            if null_fields:
                raise ValueError(
                    f"Fields cannot be null: {', '.join(sorted(null_fields))}."
                )
        return values


class OrganizationCreate(APIModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class OrganizationRead(OrganizationCreate):
    id: int
    created_at: datetime


class OrganizationUpdate(APIUpdateModel):
    NON_NULLABLE_FIELDS = frozenset({"name"})

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None


class FacilityCreate(APIModel):
    organization_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class FacilityRead(FacilityCreate):
    id: int
    created_at: datetime


class FacilityUpdate(APIUpdateModel):
    NON_NULLABLE_FIELDS = frozenset({"organization_id", "name"})

    organization_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None


class FunctionalSystemCreate(APIModel):
    facility_id: int = Field(gt=0)
    parent_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=150)
    description: str | None = None


class FunctionalSystemRead(FunctionalSystemCreate):
    id: int


class FunctionalSystemUpdate(APIUpdateModel):
    NON_NULLABLE_FIELDS = frozenset({"facility_id", "name"})

    facility_id: int | None = Field(default=None, gt=0)
    parent_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None


class PhysicalLocationCreate(APIModel):
    facility_id: int = Field(gt=0)
    parent_id: int | None = Field(default=None, gt=0)
    name: str = Field(min_length=1, max_length=150)
    location_type: Literal["BUILDING", "FLOOR", "ROOM", "AREA"]
    description: str | None = None


class PhysicalLocationRead(PhysicalLocationCreate):
    id: int


class PhysicalLocationUpdate(APIUpdateModel):
    NON_NULLABLE_FIELDS = frozenset({"facility_id", "name", "location_type"})

    facility_id: int | None = Field(default=None, gt=0)
    parent_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    location_type: Literal["BUILDING", "FLOOR", "ROOM", "AREA"] | None = None
    description: str | None = None


class MachineCreate(APIModel):
    facility_id: int = Field(gt=0)
    functional_system_id: int | None = Field(default=None, gt=0)
    physical_location_id: int | None = Field(default=None, gt=0)
    machine_name: str = Field(min_length=1, max_length=150)
    machine_code: str = Field(min_length=1, max_length=80)
    description: str | None = None
    status: str = Field(default="ACTIVE", min_length=1, max_length=30)


class MachineUpdate(APIUpdateModel):
    NON_NULLABLE_FIELDS = frozenset(
        {"facility_id", "machine_name", "machine_code", "status"}
    )

    facility_id: int | None = Field(default=None, gt=0)
    functional_system_id: int | None = Field(default=None, gt=0)
    physical_location_id: int | None = Field(default=None, gt=0)
    machine_name: str | None = Field(default=None, min_length=1, max_length=150)
    machine_code: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=30)


class MachineRead(MachineCreate):
    id: int
    created_at: datetime
    updated_at: datetime


class MaintenanceLogCreate(APIModel):
    machine_id: int = Field(gt=0)
    record_type: Literal["daily", "problem", "repair"]
    description: str = Field(min_length=1, max_length=4000)
    symptoms: str | None = Field(default=None, max_length=2000)
    repair_actions: str | None = Field(default=None, max_length=4000)
    outcome: str | None = Field(default=None, max_length=4000)
    recorded_on: date = Field(default_factory=date.today)

    @model_validator(mode="after")
    def validate_record_details(self):
        required_fields = {
            "daily": {"description": self.description},
            "problem": {"symptoms": self.symptoms, "description": self.description},
            "repair": {
                "description": self.description,
                "repair_actions": self.repair_actions,
                "outcome": self.outcome,
            },
        }[self.record_type]
        missing = [
            field_name
            for field_name, value in required_fields.items()
            if value is None or not value.strip()
        ]
        if missing:
            raise ValueError(
                f"Required details for a {self.record_type} record: "
                f"{', '.join(missing)}."
            )
        return self


class MaintenanceLogRead(MaintenanceLogCreate):
    id: int
    status: str
    created_at: datetime


class MaintenanceLogUpdate(APIUpdateModel):
    NON_NULLABLE_FIELDS = frozenset({"description", "status"})

    description: str | None = Field(default=None, min_length=1, max_length=4000)
    symptoms: str | None = Field(default=None, max_length=2000)
    repair_actions: str | None = Field(default=None, max_length=4000)
    outcome: str | None = Field(default=None, max_length=4000)
    status: Literal["OPEN", "IN_PROGRESS", "CLOSED"] | None = None


class MachineManualRead(APIModel):
    id: int
    machine_id: int
    document_id: str
    filename: str
    uploaded_at: datetime
    file_url: str | None = None


class MachineManualUpdate(APIUpdateModel):
    NON_NULLABLE_FIELDS = frozenset({"machine_id", "filename"})

    machine_id: int | None = Field(default=None, gt=0)
    filename: str | None = Field(default=None, min_length=1, max_length=255)


class ManualSearchRequest(APIModel):
    question: str = Field(min_length=1, max_length=1000)
    scope_type: Literal[
        "machine",
        "functional_system",
        "physical_location",
        "facility",
    ] = "machine"
    scope_id: int | None = Field(default=None, gt=0)
    machine_id: int | None = Field(default=None, gt=0)
    top_k: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def normalize_legacy_machine_scope(self):
        if self.scope_id is None and self.machine_id is not None:
            self.scope_id = self.machine_id
        if self.scope_id is None:
            raise ValueError("scope_id or machine_id is required.")
        if (
            self.scope_type == "machine"
            and self.machine_id is not None
            and self.scope_id != self.machine_id
        ):
            raise ValueError("machine_id must match scope_id for machine scope.")
        return self
