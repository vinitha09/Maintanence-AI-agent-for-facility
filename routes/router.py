from pathlib import Path
import re
from uuid import uuid4

import pymupdf
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from chunking import split_text
from models.maintanence import (
    Machine,
    MachineCreate,
    MachineManual,
    MaintenanceLogCreate,
    MaintenanceLog,
    MaintenanceLogRead,
)
from models.manual import ManualSearchRequest
from services.answer_service import generate_answer
from services.relavance_service import filter_relevant_chunks
from vector_store import collection
from database import engine

router = APIRouter()


def get_session():
    with Session(engine) as session:
        yield session


def _maintenance_log_text(log: MaintenanceLogRead) -> str: # Return a formatted string representation of a maintenance log, including relevant details.
    parts = [
        f"Record type: {log.record_type}",
        f"Date: {log.recorded_on.isoformat()}",
    ]
    for label, value in (
        ("Shift", log.shift),
        ("Machine status", log.machine_status),
        ("Severity", log.severity),
        ("Symptoms", log.symptoms),
        ("Problem", log.problem_description),
        ("Description and observations", log.description),
        ("Repair actions", log.actions),
        ("Outcome", log.outcome),
    ):
        if value:
            parts.append(f"{label}: {value}")
    if log.record_type == "repair":
        parts.append(f"Verified: {'Yes' if log.verified else 'No'}")
    return "\n".join(parts)





@router.get("/manuals")
def list_manuals():
    stored_chunks = collection.get(include=["metadatas"]) # Retrieve all stored chunks from the vector store, including their metadata
    documents = {}

    for metadata in stored_chunks.get("metadatas", []):
        if not metadata:
            continue

        document_id = metadata.get("document_id", metadata.get("filename"))
        if document_id is not None:
            documents[document_id] = {
                "document_id": document_id,
                "filename": metadata.get("filename", "unknown.pdf"),
            }

    return {
        "total_documents": len(documents),
        "documents": list(documents.values()),
    }


@router.get("/machines", response_model=list[Machine])
def get_machines(
    session: Session = Depends(get_session),
):
    return session.exec(
        select(Machine).order_by(Machine.name)
    ).all() # Retrieve all machines from the database, ordered by their name, and return them as a list of Machine response models.


@router.delete("/manuals/{document_id}")
def delete_manual(document_id: str):
    stored_chunks = collection.get(
        where={"document_id": document_id},
        include=["metadatas"],
    )
    chunk_ids = stored_chunks.get("ids", [])

    if not chunk_ids:
        raise HTTPException(status_code=404, detail="Manual not found.")

    collection.delete(ids=chunk_ids)
    return {
        "message": "Manual deleted successfully.",
        "document_id": document_id,
        "chunks_deleted": len(chunk_ids),
    }



@router.post("/manuals/upload")
async def upload_manual(
    machine_id: int = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(
            status_code=404,
            detail="Machine not found. Register the machine first.",
        )

    filename = file.filename
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a PDF file.",
        )

    contents = await file.read()
    document_id = str(uuid4()) # Generate a unique identifier for the uploaded manual to ensure that each manual is uniquely identifiable in the system.
    chunks = []
    metadatas = []
    ids = []

    try:
        with pymupdf.open(stream=contents, filetype="pdf") as pdf:
            for page_number, page in enumerate(pdf, start=1):
                page_text = page.get_text().strip()
                if not page_text:
                    continue

                for chunk in split_text(page_text): # Split the page text into smaller chunks for better indexing and retrieval
                    chunk_index = len(chunks)
                    chunks.append(chunk)
                    ids.append(f"{document_id}_{chunk_index}")
                    metadatas.append(
                        {
                            "document_id": document_id,
                            "machine_id": machine.id,
                            "filename": filename,
                            "page_number": page_number,
                        }
                    )
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

    manuals_dir = Path("data/manuals")
    manuals_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = manuals_dir / f"{document_id}.pdf"
    pdf_path.write_bytes(contents)

    collection.add(  # Add the extracted chunks of the manual to the vector store for efficient retrieval and search.
        ids=ids,
        documents=chunks,
        metadatas=metadatas,
    )

    manual = MachineManual(
        machine_id=machine.id,
        document_id=document_id,
        filename=filename,
    )

    session.add(manual)
    session.commit()
    session.refresh(manual)

    return {
        "message": "Manual uploaded and linked to machine successfully.",
        "machine_id": machine.id,
        "machine_name": machine.name,
        "manual_id": manual.id,
        "document_id": document_id,
        "filename": filename,
        "chunks_added": len(chunks),
    }



def _maintenance_log_responses(   
    records: list[MaintenanceLog],
) -> list[MaintenanceLogRead]:  #
    return [
        MaintenanceLogRead.model_validate(record.model_dump()) # Convert each MaintenanceLog record to a MaintenanceLogRead response model
        for record in records
    ]

def _rank_maintenance_logs( 
    logs: list[MaintenanceLogRead],
    question: str,
    limit: int = 8,
) -> list[MaintenanceLogRead]:
    terms = set(re.findall(r"[a-z0-9]{3,}", question.lower())) # Extract terms with at least 3 alphanumeric characters

    def relevance(log: MaintenanceLogRead) -> tuple[int, str, int]:
        text = _maintenance_log_text(log).lower()
        overlap = sum(term in text for term in terms) # Count how many of the extracted terms appear in the log text
        return overlap, log.recorded_on.isoformat(), log.id or 0 # Sort by overlap, then by date, then by ID

    return sorted(logs, key=relevance, reverse=True)[:limit] # Return the top 'limit' logs sorted by relevance


@router.post("/manuals/search")
def search_manuals(
    request: ManualSearchRequest, 
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, request.machine_id) 
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found.")

    records = session.exec(
        select(MaintenanceLog)
        .where(MaintenanceLog.machine_id == request.machine_id)
        .order_by(
            MaintenanceLog.recorded_on.desc(), 
            MaintenanceLog.id.desc(),
        )
    ).all()
    logs = _maintenance_log_responses(records) 
    ranked_logs = _rank_maintenance_logs(logs, request.question) # Rank the maintenance logs based on their relevance to the user's question, returning the top logs for further processing.
    log_matches = [
        {
            "source_type": "maintenance_log",
            "log_id": log.id,
            "record_type": log.record_type,
            "recorded_on": log.recorded_on.isoformat(),
            "text": _maintenance_log_text(log),
        }
        for log in ranked_logs
    ]

    manual_matches = []
    if collection.count(): # Check if there are any manuals stored in the vector store before performing a search to avoid unnecessary queries and potential errors.
        results = collection.query(
            query_texts=[request.question],
            n_results=request.top_k,
            where={"machine_id": request.machine_id},
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0] or []
        metadatas = results.get("metadatas", [[]])[0] or []
        distances = results.get("distances", [[]])[0] or []
        matches = []
        for index, chunk_text in enumerate(documents): 
            metadata = metadatas[index]
            matches.append({
                "source_type": "manual",
                "text": chunk_text,
                "filename": metadata.get("filename", "unknown.pdf"),
                "page_number": metadata.get("page_number"),
                "distance": distances[index],
            })
        manual_matches = filter_relevant_chunks(matches) 

    context_matches = log_matches + manual_matches
    if not context_matches:
        return {
            "question": request.question,
            "answer": (
                "I couldn't find sufficiently relevant information "
                "in this machine's maintenance logs or manuals. "
                "Please consult the relevant manual or a qualified technician."
            ),
            "sources": [],
        }

    answer = generate_answer(
        question=request.question,
        matches=context_matches,
    )
    if (
        not isinstance(answer, str)
        or not answer.strip()
        or answer.strip().lower() == "null"
    ):
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI service returned an empty answer. "
                "Please try again; the retrieved sources are still available."
            ),
        )

    return {
        "question": request.question,
        "answer": answer.strip(),
        "sources": [
            {
                key: value
                for key, value in match.items()
                if key in {
                    "source_type",
                    "log_id",
                    "record_type",
                    "recorded_on",
                    "filename",
                    "page_number",
                }
            }
            for match in context_matches
        ],
    }
 


@router.get("/maintenance-logs", response_model=list[MaintenanceLogRead]) 
def list_maintenance_logs(
    machine_id: int | None = Query(default=None, gt=0),
    session: Session = Depends(get_session),
):
    statement = select(MaintenanceLog)
    if machine_id is not None:
        statement = statement.where(
            MaintenanceLog.machine_id == machine_id
        )
    records = session.exec(
        statement.order_by(
            MaintenanceLog.recorded_on.desc(),
            MaintenanceLog.id.desc(),
        )
    ).all()
    return _maintenance_log_responses(records)


@router.post("/maintenance-logs", response_model=MaintenanceLogRead)
def create_maintenance_log(
    log_data: MaintenanceLogCreate,
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, log_data.machine_id)
    if machine is None:
        raise HTTPException(status_code=404, detail="Machine not found.")

    record = MaintenanceLog(
        machine_id=log_data.machine_id,
        record_type=log_data.record_type,
        recorded_on=log_data.recorded_on,
        shift=log_data.shift,
        machine_status=log_data.machine_status,
        severity=log_data.severity,
        symptoms=log_data.symptoms,
        description=log_data.description,
        problem_description=log_data.problem_description,
        actions=log_data.actions,
        outcome=log_data.outcome,
        verified=log_data.verified,
        status="open" if log_data.record_type == "problem" else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return _maintenance_log_responses([record])[0]


@router.patch(
    "/maintenance-logs/{record_id}/close",
    response_model=MaintenanceLogRead,
)
def close_problem_report(
    record_id: int,
    session: Session = Depends(get_session),
):
    record = session.get(MaintenanceLog, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Maintenance record not found.")
    if record.record_type != "problem":
        raise HTTPException(
            status_code=409,
            detail="Only problem reports can be closed.",
        )

    record.status = "closed"
    session.add(record)
    session.commit()
    session.refresh(record)
    return _maintenance_log_responses([record])[0]


@router.post("/machines", response_model=Machine)
def create_machine(
    machine_data: MachineCreate,
    session: Session = Depends(get_session),
):
    machine = Machine.model_validate(machine_data)

    session.add(machine)
    session.commit()
    session.refresh(machine)

    return machine


@router.get("/machines/{machine_id}/manuals")
def get_machine_manuals(
    machine_id: int,
    session: Session = Depends(get_session),
):
    machine = session.get(Machine, machine_id)

    if machine is None:
        raise HTTPException(
            status_code=404,
            detail="Machine not found.",
        )

    manuals = session.exec(
        select(MachineManual).where(
            MachineManual.machine_id == machine_id
        )
    ).all()

    return [
        {
            "id": manual.id,
            "document_id": manual.document_id,
            "filename": manual.filename,
            "machine_id": manual.machine_id,
            "file_url": f"/manuals/{manual.document_id}/file",
        }
        for manual in manuals
    ]


@router.get("/manuals/{document_id}/file")
def open_manual(
    document_id: str,
    session: Session = Depends(get_session),
):
    manual = session.exec(
        select(MachineManual).where(
            MachineManual.document_id == document_id
        )
    ).first()

    if manual is None:
        raise HTTPException(
            status_code=404,
            detail="Manual not found.",
        )

    pdf_path = Path("data/manuals") / f"{document_id}.pdf"

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