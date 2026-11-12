from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.dependencies import AdminUser, require_approved_user
from backend.app.db.connection import get_session
from backend.app.models.maintenance import Organization
from backend.app.schemas.facility import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
    dependencies=[Depends(require_approved_user)],
)


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    session: Session = Depends(get_session),
):
    return session.exec(select(Organization).order_by(Organization.name)).all()


@router.post("", response_model=OrganizationRead, status_code=201)
def create_organization(
    data: OrganizationCreate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    organization = Organization.model_validate(data)
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: int,
    session: Session = Depends(get_session),
):
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


@router.patch("/{organization_id}", response_model=OrganizationRead)
def update_organization(
    organization_id: int,
    data: OrganizationUpdate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    organization.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(organization)
    session.commit()
    session.refresh(organization)
    return organization


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    organization_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    organization = session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    session.delete(organization)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Organization still has facilities and cannot be deleted.",
        ) from error
