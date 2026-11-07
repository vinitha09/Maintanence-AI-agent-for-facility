from datetime import date, datetime, timezone
from typing import Literal
from sqlmodel import SQLModel, Field
from pydantic import BaseModel, model_validator


class Machine(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    machine_type: str
    manufacturer: str | None = None
    model_number: str | None = None
    location: str | None = None


class MachineManual(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id", index=True)
    document_id: str = Field(index=True)
    filename: str


class Incident(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id", index=True)
    problem: str
    symptoms: str | None = None
    status: str = "open"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Solution(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    incident_id: int = Field(foreign_key="incident.id", index=True)
    description: str
    outcome: str | None = None
    created_by: str | None = None
    is_verified: bool = False
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class MaintenanceLog(SQLModel, table=True):
    __tablename__ = "maintenance_log"

    id: int | None = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id", index=True)
    record_type: str = Field(index=True)
    recorded_on: date = Field(index=True)
    shift: str | None = None
    machine_status: str | None = None
    severity: str | None = None
    symptoms: str | None = None
    description: str | None = None
    problem_description: str | None = None
    actions: str | None = None
    outcome: str | None = None
    verified: bool = False
    status: str | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    machine_type: str = Field(min_length=1, max_length=100)
    manufacturer: str | None = None
    model_number: str | None = None
    location: str | None = None

class IncidentCreate(BaseModel):
    machine_id: int = Field(gt=0)
    problem: str = Field(min_length=1, max_length=2000)
    symptoms: str | None = None


class SolutionCreate(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    outcome: str | None = None
    created_by: str | None = None


class MaintenanceLogCreate(BaseModel):
    machine_id: int = Field(gt=0)
    record_type: Literal["daily", "problem", "repair"]
    recorded_on: date
    shift: str | None = Field(default=None, max_length=30)
    machine_status: str | None = Field(default=None, max_length=50)
    severity: str | None = Field(default=None, max_length=30)
    symptoms: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=4000)
    problem_description: str | None = Field(default=None, max_length=2000)
    actions: str | None = Field(default=None, max_length=4000)
    outcome: str | None = Field(default=None, max_length=4000)
    verified: bool = False

    @model_validator(mode="after") # run this validation after Pydantic has checked and assigned the model's fields.
    def validate_record_details(self):
        required_fields = {
            "daily": {"description": self.description},
            "problem": {
                "symptoms": self.symptoms,
                "description": self.description,
            },
            "repair": {
                "problem_description": self.problem_description,
                "actions": self.actions,
                "outcome": self.outcome,
            },
        }[self.record_type]
        missing_fields = [
            field_name
            for field_name, value in required_fields.items()
            if value is None or not value.strip()
        ]
        if missing_fields:
            raise ValueError(
                f"Required details for a {self.record_type} record: "
                f"{', '.join(missing_fields)}."
            )
        return self


class MaintenanceLogRead(BaseModel):
    id: int
    machine_id: int
    record_type: Literal["daily", "problem", "repair"]
    recorded_on: date
    shift: str | None = None
    machine_status: str | None = None
    severity: str | None = None
    symptoms: str | None = None
    description: str | None = None
    problem_description: str | None = None
    actions: str | None = None
    outcome: str | None = None
    verified: bool = False
    status: str | None = None
    created_at: datetime
