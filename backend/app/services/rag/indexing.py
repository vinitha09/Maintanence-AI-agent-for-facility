import logging

from sqlalchemy import delete
from sqlmodel import Session

from backend.app.db.connection import engine
from backend.app.models.maintenance import (
    Machine,
    MaintenanceLog,
    SearchableChunk,
)
from backend.app.services.rag.chunking import split_text
from backend.app.services.rag.embeddings import EmbeddingError, embed_texts

logger = logging.getLogger(__name__)


def maintenance_log_text(log: MaintenanceLog) -> str:
    parts = [
        f"Record type: {log.record_type}",
        f"Date: {log.recorded_on.isoformat()}",
    ]
    for label, value in (
        ("Symptoms", log.symptoms),
        ("Description", log.description),
        ("Repair actions", log.repair_actions),
        ("Outcome", log.outcome),
    ):
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def _save_chunks(session: Session, searchable_chunks: list[SearchableChunk]) -> None:
    session.add_all(searchable_chunks)
    session.commit()
    try:
        embeddings = embed_texts([chunk.text for chunk in searchable_chunks])
    except EmbeddingError:
        logger.exception(
            "Records were saved but could not be embedded; "
            "full-text retrieval remains available."
        )
        return
    for chunk, embedding in zip(searchable_chunks, embeddings):
        chunk.embedding = embedding
    session.add_all(searchable_chunks)
    session.commit()


def index_maintenance_log(log_id: int) -> None:
    with Session(engine) as session:
        log = session.get(MaintenanceLog, log_id)
        if log is None:
            logger.warning(
                "Maintenance log %s was not found for search indexing.",
                log_id,
            )
            return
        machine = session.get(Machine, log.machine_id)
        if machine is None:
            logger.warning(
                "Machine %s was not found while indexing maintenance log %s.",
                log.machine_id,
                log_id,
            )
            return

        chunks = split_text(maintenance_log_text(log))
        searchable_chunks = [
            SearchableChunk(
                facility_id=machine.facility_id,
                machine_id=machine.id,
                source_type="maintenance_log",
                source_id=str(log.id),
                chunk_index=chunk_index,
                maintenance_log_id=log.id,
                text=chunk,
            )
            for chunk_index, chunk in enumerate(chunks)
        ]
        session.exec(
            delete(SearchableChunk).where(
                SearchableChunk.source_type == "maintenance_log",
                SearchableChunk.source_id == str(log.id),
            )
        )
        _save_chunks(session, searchable_chunks)


def index_manual_chunks(
    session: Session,
    *,
    machine: Machine,
    manual_id: int,
    document_id: str,
    filename: str,
    chunks: list[str],
    page_numbers: list[int],
) -> list[SearchableChunk]:
    searchable_chunks = [
        SearchableChunk(
            facility_id=machine.facility_id,
            machine_id=machine.id,
            source_type="manual",
            source_id=document_id,
            chunk_index=chunk_index,
            manual_id=manual_id,
            document_id=document_id,
            filename=filename,
            page_number=page_numbers[chunk_index],
            text=chunk,
        )
        for chunk_index, chunk in enumerate(chunks)
    ]
    session.add_all(searchable_chunks)
    try:
        embeddings = embed_texts(chunks)
    except EmbeddingError:
        logger.exception(
            "Manual %s was saved but could not be embedded; "
            "full-text retrieval remains available.",
            document_id,
        )
        return searchable_chunks
    for chunk, embedding in zip(searchable_chunks, embeddings):
        chunk.embedding = embedding
    return searchable_chunks
