from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.dependencies import (
    AdminUser,
    ApprovedUser,
    get_current_user,
)
from backend.app.db.connection import get_session
from backend.app.models.maintenance import (
    Facility,
    FunctionalSystem,
    Machine,
    PhysicalLocation,
    SearchableChunk,
)
from backend.app.schemas.facility import MachineCreate, MachineRead, MachineUpdate

router = APIRouter(
    prefix="/machines",
    tags=["machines"],
    dependencies=[Depends(get_current_user)],
)


def _validate_machine_scope(
    session: Session,
    facility_id: int,
    functional_system_id: int | None,
    physical_location_id: int | None,
) -> None:
    if session.get(Facility, facility_id) is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    if functional_system_id is not None:
        system = session.get(FunctionalSystem, functional_system_id)
        if system is None:
            raise HTTPException(status_code=404, detail="Functional system not found.")
        if system.facility_id != facility_id:
            raise HTTPException(
                status_code=400,
                detail="Machine and functional system must belong to the same facility.",
            )
    if physical_location_id is not None:
        location = session.get(PhysicalLocation, physical_location_id)
        if location is None:
            raise HTTPException(status_code=404, detail="Physical location not found.")
        if location.facility_id != facility_id:
            raise HTTPException(
                status_code=400,
                detail="Machine and physical location must belong to the same facility.",
            )


@router.get("", response_model=list[MachineRead])
def list_machines(
    session: Session = Depends(get_session),
    facility_id: int | None = None,
    functional_system_id: int | None = None,
    physical_location_id: int | None = None,
):
    statement = select(Machine).where(Machine.is_deleted.is_(False))
    if facility_id is not None:
        statement = statement.where(Machine.facility_id == facility_id)
    if functional_system_id is not None:
        statement = statement.where(
            Machine.functional_system_id == functional_system_id
        )
    if physical_location_id is not None:
        statement = statement.where(
            Machine.physical_location_id == physical_location_id
        )
    return session.exec(statement.order_by(Machine.machine_name)).all()


@router.post("", response_model=MachineRead, status_code=status.HTTP_201_CREATED)
def create_machine(
    machine_data: MachineCreate,
    _: ApprovedUser,
    session: Session = Depends(get_session),
):
    _validate_machine_scope(
        session,
        machine_data.facility_id,
        machine_data.functional_system_id,
        machine_data.physical_location_id,
    )
    machine = Machine.model_validate(machine_data)
    session.add(machine)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Machine code already exists in this facility.",
        ) from error
    session.refresh(machine)
    return machine


@router.get("/{machine_id}", response_model=MachineRead)
def get_machine(
    machine_id: int,
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found.")
    return machine


@router.patch("/{machine_id}", response_model=MachineRead)
def update_machine(
    machine_id: int,
    machine_data: MachineUpdate,
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found.")
    updates = machine_data.model_dump(exclude_unset=True)
    facility_id = updates.get("facility_id", machine.facility_id)
    functional_system_id = updates.get(
        "functional_system_id",
        machine.functional_system_id,
    )
    physical_location_id = updates.get(
        "physical_location_id",
        machine.physical_location_id,
    )
    original_facility_id = machine.facility_id
    _validate_machine_scope(
        session,
        facility_id,
        functional_system_id,
        physical_location_id,
    )
    updates["updated_at"] = datetime.now(timezone.utc)
    machine.sqlmodel_update(updates)
    session.add(machine)
    if facility_id != original_facility_id:
        session.exec(
            update(SearchableChunk)
            .where(SearchableChunk.machine_id == machine_id)
            .values(facility_id=facility_id)
        )
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Machine code already exists in this facility.",
        ) from error
    session.refresh(machine)
    return machine


@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_machine(
    machine_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found.")
    machine.is_deleted = True
    machine.updated_at = datetime.now(timezone.utc)
    session.add(machine)
    session.commit()
