import uuid
from typing import List, Dict, Any
from retrieval.vector_store import InMemoryVectorStore, Chunk
from llm.openai_client import OpenAIClient

def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i+chunk_size])
        i += max(1, chunk_size - overlap)
    return chunks

def ingest_documents(
    docs: List[Dict[str, Any]],
    store: InMemoryVectorStore,
    openai: OpenAIClient,
) -> None:
    """
    docs: [{"text": "...", "metadata": {"source": "pdf1", "title": "..."}}, ...]
    """
    all_chunks: List[Chunk] = []
    all_texts: List[str] = []

    for doc in docs:
        for part in chunk_text(doc["text"]):
            all_texts.append(part)
            all_chunks.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    text=part,
                    metadata=doc.get("metadata", {}),
                )
            )

    if not all_texts:
        return

    embeddings = openai.embed(all_texts)
    store.add(embeddings, all_chunks)
