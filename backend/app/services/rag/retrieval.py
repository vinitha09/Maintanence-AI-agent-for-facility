from collections import defaultdict

from sqlalchemy import bindparam, text as sql_text
from sqlalchemy.orm import load_only
from sqlmodel import Session, select

from backend.app.models.maintenance import SearchableChunk
from backend.app.services.rag.embeddings import embed_texts

RRF_CONSTANT = 60
HNSW_EF_SEARCH = 100
MAX_COSINE_DISTANCE = 0.7


def reciprocal_rank_fusion(
    rankings: list[list[int]],
    limit: int,
    constant: int = RRF_CONSTANT,
) -> list[int]:
    scores: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] += 1 / (constant + rank)
    return [
        chunk_id
        for chunk_id, _ in sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )[:limit]
    ]


def hybrid_search(
    session: Session,
    question: str,
    limit: int,
    machine_id: int | None = None,
    machine_ids: list[int] | None = None,
    source_types: list[str] | None = None,
    document_id: str | None = None,
) -> list[SearchableChunk]:
    scoped_machine_ids = machine_ids or (
        [machine_id] if machine_id is not None else []
    )
    if not scoped_machine_ids:
        raise ValueError("At least one machine ID is required for retrieval.")
    query_embedding = embed_texts([question])[0]
    candidate_limit = max(limit * 3, limit)

    filters = [
        SearchableChunk.machine_id.in_(scoped_machine_ids),
        SearchableChunk.embedding.is_not(None),
    ]
    if source_types:
        filters.append(SearchableChunk.source_type.in_(source_types))
    if document_id is not None:
        filters.append(SearchableChunk.document_id == document_id)

    session.execute(sql_text(f"SET LOCAL hnsw.ef_search = {HNSW_EF_SEARCH}"))
    vector_distance = SearchableChunk.embedding.cosine_distance(
        query_embedding
    ).label("distance")
    vector_statement = (
        select(SearchableChunk.id, vector_distance)
        .where(*filters)
        .order_by(
            SearchableChunk.embedding.cosine_distance(query_embedding)
        )
        .limit(candidate_limit)
    )
    vector_rows = session.execute(vector_statement).all()
    vector_ids = [
        row.id
        for row in vector_rows
        if row.distance <= MAX_COSINE_DISTANCE
    ]

    document_filter = (
        "AND document_id = :document_id"
        if document_id is not None
        else ""
    )
    full_text_sql = f"""
        SELECT id
        FROM searchable_chunk
        WHERE search_vector @@ plainto_tsquery('english', :query)
          AND machine_id IN :machine_ids
          AND source_type IN :source_types
          {document_filter}
        ORDER BY ts_rank(
            search_vector,
            plainto_tsquery('english', :query)
        ) DESC, id
        LIMIT :candidate_limit
    """
    full_text_statement = sql_text(full_text_sql).bindparams(
        bindparam("source_types", expanding=True),
        bindparam("machine_ids", expanding=True),
    )
    effective_source_types = source_types or [
        "maintenance_log",
        "manual",
    ]
    full_text_parameters = {
        "query": question,
        "machine_ids": scoped_machine_ids,
        "source_types": effective_source_types,
        "candidate_limit": candidate_limit,
    }
    if document_id is not None:
        full_text_parameters["document_id"] = document_id
    full_text_rows = session.execute(full_text_statement, full_text_parameters)
    full_text_ids = [row.id for row in full_text_rows]

    ranked_ids = reciprocal_rank_fusion(
        [vector_ids, full_text_ids],
        limit=limit,
    )
    if not ranked_ids:
        return []

    fields = (
        SearchableChunk.id,
        SearchableChunk.machine_id,
        SearchableChunk.source_type,
        SearchableChunk.source_id,
        SearchableChunk.manual_id,
        SearchableChunk.maintenance_log_id,
        SearchableChunk.document_id,
        SearchableChunk.filename,
        SearchableChunk.page_number,
        SearchableChunk.text,
    )
    chunks = session.exec(
        select(SearchableChunk)
        .options(load_only(*fields))
        .where(SearchableChunk.id.in_(ranked_ids))
    ).all()
    chunks_by_id = {chunk.id: chunk for chunk in chunks}
    return [
        chunks_by_id[chunk_id]
        for chunk_id in ranked_ids
        if chunk_id in chunks_by_id
    ]
