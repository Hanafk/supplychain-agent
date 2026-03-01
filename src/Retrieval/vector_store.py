from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np

@dataclass
class Chunk:
    id: str
    text: str
    metadata: Dict[str, Any]

class InMemoryVectorStore:
    """
    Simple store en mémoire (ok pour démarrer).
    Tu peux remplacer par FAISS/Chroma/pgvector ensuite sans changer l'agent.
    """
    def __init__(self):
        self.vectors: np.ndarray | None = None  # shape (n, d)
        self.chunks: List[Chunk] = []

    def add(self, embeddings: List[List[float]], chunks: List[Chunk]) -> None:
        X = np.array(embeddings, dtype=np.float32)
        if self.vectors is None:
            self.vectors = X
        else:
            self.vectors = np.vstack([self.vectors, X])
        self.chunks.extend(chunks)

    def search(self, query_embedding: List[float], k: int = 5) -> List[Chunk]:
        if self.vectors is None or len(self.chunks) == 0:
            return []

        q = np.array(query_embedding, dtype=np.float32)
        # cosine similarity
        X = self.vectors
        X_norm = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        q_norm = q / (np.linalg.norm(q) + 1e-9)
        sims = X_norm @ q_norm

        top_idx = np.argsort(-sims)[:k]
        return [self.chunks[i] for i in top_idx]
