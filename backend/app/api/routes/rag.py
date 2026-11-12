import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from backend.app.api.dependencies import require_approved_user
from backend.app.db.connection import get_session
from backend.app.models.maintenance import (
    Facility,
    FunctionalSystem,
    Machine,
    MaintenanceLog,
    PhysicalLocation,
)
from backend.app.schemas.facility import ManualSearchRequest
from backend.app.services.rag.answer_generation import (
    AnswerGenerationError,
    generate_answer,
    log_generation_metrics,
    open_answer_stream,
)
from backend.app.services.rag.embeddings import EmbeddingError
from backend.app.services.rag.retrieval import hybrid_search

router = APIRouter(dependencies=[Depends(require_approved_user)])
logger = logging.getLogger(__name__)
NO_EVIDENCE_ANSWER = (
    "I couldn't find sufficiently relevant information in the selected scope's "
    "maintenance logs or manuals. Please consult the relevant manual or a "
    "qualified technician."
)
SOURCE_FIELDS = {
    "source_type",
    "log_id",
    "record_type",
    "recorded_on",
    "filename",
    "page_number",
}


def _get_context_matches(
    request: ManualSearchRequest,
    session: Session,
) -> list[dict]:
    if request.scope_type == "machine":
        machine = session.get(Machine, request.scope_id)
        if machine is None or machine.is_deleted:
            raise HTTPException(status_code=404, detail="Machine not found.")
        machine_ids = [machine.id]
    elif request.scope_type == "physical_location":
        location = session.get(PhysicalLocation, request.scope_id)
        if location is None:
            raise HTTPException(status_code=404, detail="Physical location not found.")
        machine_ids = _machines_in_physical_subtree(session, location)
    elif request.scope_type == "facility":
        facility = session.get(Facility, request.scope_id)
        if facility is None:
            raise HTTPException(status_code=404, detail="Facility not found.")
        machine_ids = session.exec(
            select(Machine.id).where(
                Machine.facility_id == facility.id,
                Machine.is_deleted.is_(False),
            )
        ).all()
    else:
        system = session.get(FunctionalSystem, request.scope_id)
        if system is None:
            raise HTTPException(status_code=404, detail="Functional system not found.")
        machine_ids = _machines_in_functional_subtree(session, system)

    if not machine_ids:
        return []
    try:
        chunks = hybrid_search(
            session=session,
            question=request.question,
            machine_ids=machine_ids,
            limit=request.top_k,
        )
    except EmbeddingError as error:
        logger.exception("Could not embed a manual-search question.")
        raise HTTPException(
            status_code=503,
            detail="Question embedding failed. Please try again.",
        ) from error

    log_matches = []
    manual_matches = []
    for chunk in chunks:
        if chunk.source_type == "maintenance_log":
            log = session.get(MaintenanceLog, chunk.maintenance_log_id)
            if log is None:
                logger.warning(
                    "Search result references missing maintenance log %s.",
                    chunk.maintenance_log_id,
                )
                continue
            if log.is_deleted:
                continue
            log_matches.append(
                {
                    "source_type": "maintenance_log",
                    "log_id": log.id,
                    "record_type": log.record_type,
                    "recorded_on": log.recorded_on.isoformat(),
                    "text": chunk.text,
                }
            )
        elif chunk.source_type == "manual":
            manual_matches.append(
                {
                    "source_type": "manual",
                    "text": chunk.text,
                    "filename": chunk.filename or "unknown.pdf",
                    "page_number": chunk.page_number,
                }
            )
    return log_matches + manual_matches


def _machines_in_functional_subtree(
    session: Session,
    root: FunctionalSystem,
) -> list[int]:
    system_ids = {root.id}
    pending = [root.id]
    while pending:
        parent_id = pending.pop()
        child_ids = session.exec(
            select(FunctionalSystem.id).where(
                FunctionalSystem.parent_id == parent_id,
                FunctionalSystem.facility_id == root.facility_id,
            )
        ).all()
        for child_id in child_ids:
            if child_id not in system_ids:
                system_ids.add(child_id)
                pending.append(child_id)
    return session.exec(
        select(Machine.id).where(
            Machine.functional_system_id.in_(system_ids),
            Machine.is_deleted.is_(False),
        )
    ).all()


def _machines_in_physical_subtree(
    session: Session,
    root: PhysicalLocation,
) -> list[int]:
    location_ids = {root.id}
    pending = [root.id]
    while pending:
        parent_id = pending.pop()
        child_ids = session.exec(
            select(PhysicalLocation.id).where(
                PhysicalLocation.parent_id == parent_id,
                PhysicalLocation.facility_id == root.facility_id,
            )
        ).all()
        for child_id in child_ids:
            if child_id not in location_ids:
                location_ids.add(child_id)
                pending.append(child_id)
    return session.exec(
        select(Machine.id).where(
            Machine.physical_location_id.in_(location_ids),
            Machine.is_deleted.is_(False),
        )
    ).all()


def _public_sources(matches: list[dict]) -> list[dict]:
    return [
        {key: value for key, value in match.items() if key in SOURCE_FIELDS}
        for match in matches
    ]


@router.post("/manuals/search")
def search_manuals(
    request: ManualSearchRequest,
    session: Session = Depends(get_session),
):
    context_matches = _get_context_matches(request, session)
    if not context_matches:
        answer = NO_EVIDENCE_ANSWER
    else:
        try:
            answer = generate_answer(
                question=request.question,
                matches=context_matches,
            )
        except AnswerGenerationError as error:
            logger.exception("Could not generate an answer with Ollama.")
            raise HTTPException(
                status_code=502,
                detail=str(error),
            ) from error
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
        "sources": _public_sources(context_matches),
    }


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/manuals/search/stream")
def stream_manual_search(
    request: ManualSearchRequest,
    session: Session = Depends(get_session),
):
    context_matches = _get_context_matches(request, session)
    sources = _public_sources(context_matches)
    upstream = None
    started_at = time.perf_counter()

    if context_matches:
        try:
            upstream = open_answer_stream(request.question, context_matches)
            tokens = iter(upstream.tokens())
            first_token = next(tokens, None)
            if first_token is None:
                raise AnswerGenerationError(
                    "Ollama completed without generating an answer."
                )
        except AnswerGenerationError as error:
            if upstream is not None:
                upstream.close()
            logger.exception("Could not start the Ollama answer stream.")
            raise HTTPException(status_code=502, detail=str(error)) from error
    else:
        tokens = iter(())
        first_token = NO_EVIDENCE_ANSWER

    def generate_events():
        try:
            if first_token:
                yield _sse_event("token", {"text": first_token})
            for token in tokens:
                yield _sse_event("token", {"text": token})
            if upstream is not None and upstream.metrics is not None:
                log_generation_metrics(upstream.metrics, started_at)
            yield _sse_event("sources", {"sources": sources})
            yield _sse_event("done", {})
        except AnswerGenerationError:
            logger.exception("Ollama answer stream failed.")
            yield _sse_event(
                "error",
                {"detail": "The AI answer stream was interrupted. Please retry."},
            )
        finally:
            if upstream is not None:
                upstream.close()

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
