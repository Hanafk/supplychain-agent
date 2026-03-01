from typing import List
from retrieval.vector_store import InMemoryVectorStore, Chunk
from llm.openai_client import OpenAIClient

class Retriever:
    def __init__(self, store: InMemoryVectorStore, openai: OpenAIClient):
        self.store = store
        self.openai = openai

    def retrieve(self, query: str, k: int = 5) -> List[Chunk]:
        q_emb = self.openai.embed([query])[0]
        return self.store.search(q_emb, k=k)
