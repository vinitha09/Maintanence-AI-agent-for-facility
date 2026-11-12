from sentence_transformers import SentenceTransformer

from backend.app.models.maintenance import EMBEDDING_DIMENSIONS

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingError(RuntimeError):
    pass


embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
actual_dimensions = embedding_model.get_embedding_dimension()
if actual_dimensions != EMBEDDING_DIMENSIONS:
    raise RuntimeError(
        f"{EMBEDDING_MODEL_NAME} returns {actual_dimensions} dimensions; "
        f"the PostgreSQL vector column is configured for {EMBEDDING_DIMENSIONS}."
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    try:
        vectors = embedding_model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception as error:
        raise EmbeddingError("Embedding generation failed.") from error
    if vectors.shape != (len(texts), EMBEDDING_DIMENSIONS):
        raise EmbeddingError(
            "The embedding model returned an unexpected vector shape: "
            f"{vectors.shape}."
        )
    return vectors.tolist()
