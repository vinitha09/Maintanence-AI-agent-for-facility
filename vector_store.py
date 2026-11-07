import chromadb
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction,
)

embedding_function = SentenceTransformerEmbeddingFunction(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

client = chromadb.PersistentClient(path="./data/chroma")

collection = client.get_or_create_collection(
    name="machine_manuals",
    embedding_function=embedding_function,
    metadata={"hnsw:space": "cosine"},
)