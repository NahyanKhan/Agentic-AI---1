"""Chroma vector store used by the retrieval agent."""

from pathlib import Path
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from reviewcrew.knowledge import documents


def open_store(persist_directory: str = ".reviewcrew/chroma") -> Chroma:
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2", encode_kwargs={"normalize_embeddings": True})
    store = Chroma(collection_name="python_review_guidance", embedding_function=embeddings, persist_directory=str(Path(persist_directory)))
    docs = documents()
    ids = [f"guide-{i}" for i in range(len(docs))]
    # Stable IDs make launch-time synchronization idempotent.
    store.add_documents(docs, ids=ids)
    return store


def retrieve(store: Chroma, query: str, k: int = 4) -> list:
    return store.similarity_search(query, k=k)
