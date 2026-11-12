from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.dependencies import AdminUser, require_approved_user
from backend.app.db.connection import get_session
from backend.app.models.maintenance import Facility, Organization
from backend.app.schemas.facility import (
    FacilityCreate,
    FacilityRead,
    FacilityUpdate,
)

router = APIRouter(
    prefix="/facilities",
    tags=["facilities"],
    dependencies=[Depends(require_approved_user)],
)


def _validate_organization(session: Session, organization_id: int) -> None:
    if session.get(Organization, organization_id) is None:
        raise HTTPException(status_code=404, detail="Organization not found.")


@router.get("", response_model=list[FacilityRead])
def list_facilities(
    session: Session = Depends(get_session),
    organization_id: int | None = None,
):
    statement = select(Facility)
    if organization_id is not None:
        statement = statement.where(Facility.organization_id == organization_id)
    return session.exec(statement.order_by(Facility.name)).all()


@router.post("", response_model=FacilityRead, status_code=201)
def create_facility(
    data: FacilityCreate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    _validate_organization(session, data.organization_id)
    facility = Facility.model_validate(data)
    session.add(facility)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A facility with this name already exists in the organization.",
        ) from error
    session.refresh(facility)
    return facility


@router.get("/{facility_id}", response_model=FacilityRead)
def get_facility(
    facility_id: int,
    session: Session = Depends(get_session),
):
    facility = session.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    return facility


@router.patch("/{facility_id}", response_model=FacilityRead)
def update_facility(
    facility_id: int,
    data: FacilityUpdate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    facility = session.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    updates = data.model_dump(exclude_unset=True)
    if "organization_id" in updates:
        _validate_organization(session, updates["organization_id"])
    facility.sqlmodel_update(updates)
    session.add(facility)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A facility with this name already exists in the organization.",
        ) from error
    session.refresh(facility)
    return facility


@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_facility(
    facility_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    facility = session.get(Facility, facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    session.delete(facility)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Facility still contains hierarchy or machine records.",
        ) from error
