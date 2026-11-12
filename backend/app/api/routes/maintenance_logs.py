import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import delete
from sqlmodel import Session, select

from backend.app.api.dependencies import AdminUser, CurrentUser, get_current_user
from backend.app.db.connection import get_session
from backend.app.models.maintenance import Machine, MaintenanceLog, SearchableChunk
from backend.app.schemas.facility import (
    MaintenanceLogCreate,
    MaintenanceLogRead,
    MaintenanceLogUpdate,
)
from backend.app.services.rag.indexing import index_maintenance_log

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/maintenance-logs",
    tags=["maintenance logs"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[MaintenanceLogRead])
def list_maintenance_logs(
    session: Session = Depends(get_session),
    machine_id: int | None = None,
):
    statement = select(MaintenanceLog).where(MaintenanceLog.is_deleted.is_(False))
    if machine_id is not None:
        statement = statement.where(MaintenanceLog.machine_id == machine_id)
    return session.exec(
        statement.order_by(
            MaintenanceLog.recorded_on.desc(),
            MaintenanceLog.id.desc(),
        )
    ).all()


@router.post("", response_model=MaintenanceLogRead, status_code=201)
def create_maintenance_log(
    log_data: MaintenanceLogCreate,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, log_data.machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found.")
    record = MaintenanceLog(
        **log_data.model_dump(),
        user_id=user.id,
        status="OPEN",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    if record.id is None:
        raise RuntimeError("The maintenance log was saved without an ID.")
    background_tasks.add_task(index_maintenance_log, record.id)
    return record


@router.get("/{record_id}", response_model=MaintenanceLogRead)
def get_maintenance_log(
    record_id: int,
    session: Session = Depends(get_session),
):
    record = session.get(MaintenanceLog, record_id)
    if record is None or record.is_deleted:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    return record


@router.patch("/{record_id}", response_model=MaintenanceLogRead)
def update_maintenance_log(
    record_id: int,
    updates_data: MaintenanceLogUpdate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    record = session.get(MaintenanceLog, record_id)
    if record is None or record.is_deleted:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    updates = updates_data.model_dump(exclude_unset=True)
    if not updates:
        return record
    combined = {
        "machine_id": record.machine_id,
        "record_type": record.record_type,
        "description": updates.get("description", record.description),
        "symptoms": updates.get("symptoms", record.symptoms),
        "repair_actions": updates.get("repair_actions", record.repair_actions),
        "outcome": updates.get("outcome", record.outcome),
        "recorded_on": record.recorded_on,
    }
    MaintenanceLogCreate.model_validate(combined)
    record.sqlmodel_update(updates)
    session.add(record)
    session.commit()
    session.refresh(record)
    if record.id is not None:
        background_tasks.add_task(index_maintenance_log, record.id)
    return record


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_maintenance_log(
    record_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    record = session.get(MaintenanceLog, record_id)
    if record is None or record.is_deleted:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    record.is_deleted = True
    session.add(record)
    session.exec(
        delete(SearchableChunk).where(
            SearchableChunk.maintenance_log_id == record_id
        )
    )
    session.commit()
