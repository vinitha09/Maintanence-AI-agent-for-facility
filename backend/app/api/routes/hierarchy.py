from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from backend.app.api.dependencies import AdminUser, require_approved_user
from backend.app.db.connection import get_session
from backend.app.models.maintenance import (
    Facility,
    FunctionalSystem,
    Machine,
    PhysicalLocation,
)
from backend.app.schemas.facility import (
    FunctionalSystemCreate,
    FunctionalSystemRead,
    FunctionalSystemUpdate,
    PhysicalLocationCreate,
    PhysicalLocationRead,
    PhysicalLocationUpdate,
)

router = APIRouter(
    prefix="/hierarchy",
    tags=["hierarchy"],
    dependencies=[Depends(require_approved_user)],
)
HierarchyNode = TypeVar("HierarchyNode", FunctionalSystem, PhysicalLocation)


def _validate_facility(session: Session, facility_id: int) -> None:
    if session.get(Facility, facility_id) is None:
        raise HTTPException(status_code=404, detail="Facility not found.")


def _validate_parent(
    session: Session,
    model: type[HierarchyNode],
    facility_id: int,
    parent_id: int | None,
    node_id: int | None = None,
) -> None:
    _validate_facility(session, facility_id)
    if parent_id is None:
        return
    parent = session.get(model, parent_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent hierarchy node not found.")
    if parent.facility_id != facility_id:
        raise HTTPException(
            status_code=400,
            detail="Parent and child must belong to the same facility.",
        )

    visited: set[int] = set()
    current = parent
    while current is not None and current.id is not None:
        if current.id == node_id:
            raise HTTPException(
                status_code=400,
                detail="A hierarchy node cannot be moved beneath itself or its descendants.",
            )
        if current.id in visited:
            raise HTTPException(status_code=409, detail="Hierarchy contains a cycle.")
        visited.add(current.id)
        current = session.get(model, current.parent_id) if current.parent_id else None


def _delete_node(session: Session, model: type[HierarchyNode], node_id: int) -> None:
    node = session.get(model, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Hierarchy node not found.")
    session.delete(node)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="Hierarchy node is still referenced by child nodes or machines.",
        ) from error


def _validate_facility_move(
    session: Session,
    model: type[HierarchyNode],
    node_id: int,
    old_facility_id: int,
    new_facility_id: int,
) -> None:
    if old_facility_id == new_facility_id:
        return
    has_children = session.exec(
        select(model.id).where(model.parent_id == node_id).limit(1)
    ).first()
    machine_field = (
        Machine.functional_system_id
        if model is FunctionalSystem
        else Machine.physical_location_id
    )
    has_machines = session.exec(
        select(Machine.id).where(machine_field == node_id).limit(1)
    ).first()
    if has_children is not None or has_machines is not None:
        raise HTTPException(
            status_code=409,
            detail="A hierarchy node with children or assigned machines cannot change facilities.",
        )


def _commit_node(session: Session, node: HierarchyNode, conflict_detail: str) -> None:
    session.add(node)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(status_code=409, detail=conflict_detail) from error


@router.get("/functional-systems", response_model=list[FunctionalSystemRead])
def list_functional_systems(
    session: Session = Depends(get_session),
    facility_id: int | None = None,
):
    statement = select(FunctionalSystem)
    if facility_id is not None:
        statement = statement.where(FunctionalSystem.facility_id == facility_id)
    return session.exec(statement.order_by(FunctionalSystem.name)).all()


@router.post(
    "/functional-systems",
    response_model=FunctionalSystemRead,
    status_code=status.HTTP_201_CREATED,
)
def create_functional_system(
    data: FunctionalSystemCreate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    _validate_parent(
        session,
        FunctionalSystem,
        data.facility_id,
        data.parent_id,
    )
    node = FunctionalSystem.model_validate(data)
    _commit_node(
        session,
        node,
        "A system with this name already exists at that hierarchy level.",
    )
    session.refresh(node)
    return node


@router.get(
    "/functional-systems/{node_id}",
    response_model=FunctionalSystemRead,
)
def get_functional_system(
    node_id: int,
    session: Session = Depends(get_session),
):
    node = session.get(FunctionalSystem, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Functional system not found.")
    return node


@router.patch("/functional-systems/{node_id}", response_model=FunctionalSystemRead)
def update_functional_system(
    node_id: int,
    data: FunctionalSystemUpdate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    node = session.get(FunctionalSystem, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Functional system not found.")
    updates = data.model_dump(exclude_unset=True)
    facility_id = updates.get("facility_id", node.facility_id)
    parent_id = updates.get("parent_id", node.parent_id)
    _validate_facility_move(
        session,
        FunctionalSystem,
        node_id,
        node.facility_id,
        facility_id,
    )
    _validate_parent(session, FunctionalSystem, facility_id, parent_id, node_id)
    node.sqlmodel_update(updates)
    _commit_node(
        session,
        node,
        "A system with this name already exists at that hierarchy level.",
    )
    session.refresh(node)
    return node


@router.delete("/functional-systems/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_functional_system(
    node_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    _delete_node(session, FunctionalSystem, node_id)


@router.get("/physical-locations", response_model=list[PhysicalLocationRead])
def list_physical_locations(
    session: Session = Depends(get_session),
    facility_id: int | None = None,
):
    statement = select(PhysicalLocation)
    if facility_id is not None:
        statement = statement.where(PhysicalLocation.facility_id == facility_id)
    return session.exec(statement.order_by(PhysicalLocation.name)).all()


@router.post(
    "/physical-locations",
    response_model=PhysicalLocationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_physical_location(
    data: PhysicalLocationCreate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    _validate_parent(session, PhysicalLocation, data.facility_id, data.parent_id)
    node = PhysicalLocation.model_validate(data)
    _commit_node(
        session,
        node,
        "A location with this name already exists at that hierarchy level.",
    )
    session.refresh(node)
    return node


@router.get(
    "/physical-locations/{node_id}",
    response_model=PhysicalLocationRead,
)
def get_physical_location(
    node_id: int,
    session: Session = Depends(get_session),
):
    node = session.get(PhysicalLocation, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Physical location not found.")
    return node


@router.patch("/physical-locations/{node_id}", response_model=PhysicalLocationRead)
def update_physical_location(
    node_id: int,
    data: PhysicalLocationUpdate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    node = session.get(PhysicalLocation, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Physical location not found.")
    updates = data.model_dump(exclude_unset=True)
    facility_id = updates.get("facility_id", node.facility_id)
    parent_id = updates.get("parent_id", node.parent_id)
    _validate_facility_move(
        session,
        PhysicalLocation,
        node_id,
        node.facility_id,
        facility_id,
    )
    _validate_parent(session, PhysicalLocation, facility_id, parent_id, node_id)
    node.sqlmodel_update(updates)
    _commit_node(
        session,
        node,
        "A location with this name already exists at that hierarchy level.",
    )
    session.refresh(node)
    return node


@router.delete("/physical-locations/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_physical_location(
    node_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    _delete_node(session, PhysicalLocation, node_id)
