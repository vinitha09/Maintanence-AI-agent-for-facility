import logging
from pathlib import Path
from uuid import uuid4

import pymupdf
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import delete, update
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from backend.app.api.dependencies import (
    AdminUser,
    get_current_user,
)
from backend.app.db.connection import get_session
from backend.app.models.maintenance import (
    Machine,
    MachineManual,
    SearchableChunk,
)
from backend.app.schemas.facility import MachineManualRead, MachineManualUpdate
from backend.app.services.rag.chunking import split_text
from backend.app.services.rag.indexing import index_manual_chunks

router = APIRouter(
    tags=["machine manuals"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)
MANUALS_DIR = Path(__file__).resolve().parents[3] / "data" / "manuals"
MAX_MANUAL_BYTES = 25 * 1024 * 1024


@router.get("/manuals", response_model=list[MachineManualRead])
def list_manuals(
    session: Session = Depends(get_session),
):
    return session.exec(
        select(MachineManual)
        .join(Machine)
        .where(Machine.is_deleted.is_(False))
        .order_by(MachineManual.id)
    ).all()


@router.post("/manuals/upload", status_code=status.HTTP_201_CREATED)
async def upload_manual(
    admin: AdminUser,
    machine_id: int = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(
            status_code=404,
            detail="Machine not found. Register the machine first.",
        )
    filename = Path(file.filename or "").name
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file.")

    contents = await file.read(MAX_MANUAL_BYTES + 1)
    if len(contents) > MAX_MANUAL_BYTES:
        raise HTTPException(
            status_code=413,
            detail="PDF files must be 25 MB or smaller.",
        )
    document_id = str(uuid4())
    chunks: list[str] = []
    page_numbers: list[int] = []
    try:
        with pymupdf.open(stream=contents, filetype="pdf") as pdf:
            for page_number, page in enumerate(pdf, start=1):
                page_text = page.get_text().strip()
                if not page_text:
                    continue
                for chunk in split_text(page_text):
                    chunks.append(chunk)
                    page_numbers.append(page_number)
    except pymupdf.FileDataError as error:
        raise HTTPException(
            status_code=400,
            detail="Could not read this PDF file.",
        ) from error

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No readable text found in the PDF. It may be scanned.",
        )

    MANUALS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = MANUALS_DIR / f"{document_id}.pdf"
    pdf_path.write_bytes(contents)
    manual = MachineManual(
        machine_id=machine.id,
        document_id=document_id,
        filename=filename,
        file_path=str(pdf_path),
    )
    session.add(manual)
    try:
        session.flush()
        if machine.id is None or manual.id is None:
            raise RuntimeError("Could not allocate machine and manual identifiers.")
        index_manual_chunks(
            session,
            machine=machine,
            manual_id=manual.id,
            document_id=document_id,
            filename=filename,
            chunks=chunks,
            page_numbers=page_numbers,
        )
        session.commit()
        session.refresh(manual)
    except SQLAlchemyError:
        session.rollback()
        pdf_path.unlink(missing_ok=True)
        raise

    return {
        "message": "Manual uploaded and linked to machine successfully.",
        "machine_id": machine.id,
        "machine_name": machine.machine_name,
        "manual_id": manual.id,
        "document_id": document_id,
        "filename": filename,
        "chunks_added": len(chunks),
    }


@router.get("/machines/{machine_id}/manuals", response_model=list[MachineManualRead])
def get_machine_manuals(
    machine_id: int,
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Machine not found.")
    manuals = session.exec(
        select(MachineManual)
        .where(MachineManual.machine_id == machine_id)
        .order_by(MachineManual.uploaded_at.desc())
    ).all()
    return [
        {
            **manual.model_dump(),
            "file_url": f"/manuals/{manual.document_id}/file",
        }
        for manual in manuals
    ]


@router.get("/manuals/{manual_id}", response_model=MachineManualRead)
def get_manual(
    manual_id: int,
    session: Session = Depends(get_session),
):
    manual = session.get(MachineManual, manual_id)
    machine = session.get(Machine, manual.machine_id) if manual else None
    if manual is None or machine is None or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Manual not found.")
    return {
        **manual.model_dump(),
        "file_url": f"/manuals/{manual.document_id}/file",
    }


@router.patch("/manuals/{manual_id}", response_model=MachineManualRead)
def update_manual(
    manual_id: int,
    data: MachineManualUpdate,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    manual = session.get(MachineManual, manual_id)
    if manual is None:
        raise HTTPException(status_code=404, detail="Manual not found.")
    updates = data.model_dump(exclude_unset=True)
    if "filename" in updates:
        session.exec(
            update(SearchableChunk)
            .where(SearchableChunk.manual_id == manual.id)
            .values(filename=updates["filename"])
        )
    if "machine_id" in updates:
        machine = session.get(Machine, updates["machine_id"])
        if machine is None or machine.is_deleted:
            raise HTTPException(status_code=404, detail="Machine not found.")
        session.exec(
            update(SearchableChunk)
            .where(SearchableChunk.manual_id == manual.id)
            .values(
                machine_id=machine.id,
                facility_id=machine.facility_id,
            )
        )
    manual.sqlmodel_update(updates)
    session.add(manual)
    session.commit()
    session.refresh(manual)
    return {
        **manual.model_dump(),
        "file_url": f"/manuals/{manual.document_id}/file",
    }


@router.get("/manuals/{document_id}/file")
def open_manual(
    document_id: str,
    session: Session = Depends(get_session),
):
    manual = session.exec(
        select(MachineManual).where(MachineManual.document_id == document_id)
    ).first()
    machine = session.get(Machine, manual.machine_id) if manual else None
    if manual is None or machine is None or machine.is_deleted:
        raise HTTPException(status_code=404, detail="Manual not found.")

    pdf_path = Path(manual.file_path)
    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Original PDF is not available. Please upload the manual again.",
        )
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=manual.filename,
        content_disposition_type="inline",
    )


@router.delete("/manuals/{manual_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_manual(
    manual_id: int,
    admin: AdminUser,
    session: Session = Depends(get_session),
):
    manual = session.get(MachineManual, manual_id)
    if manual is None:
        raise HTTPException(status_code=404, detail="Manual not found.")
    pdf_path = Path(manual.file_path)
    session.exec(
        delete(SearchableChunk).where(SearchableChunk.manual_id == manual.id)
    )
    session.delete(manual)
    session.commit()
    try:
        pdf_path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Could not remove manual file %s.", pdf_path)
