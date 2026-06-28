"""
rag_engine.py
Core RAG logic: chunking, embedding, storing, and retrieving.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
CHUNK_SIZE   = int(os.getenv("CHUNK_SIZE", "400"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "80"))
TOP_K        = int(os.getenv("TOP_K", "5"))
COLLECTION   = "knowledge_base"

_embedder: Optional[SentenceTransformer] = None
_chroma_client = None
_collection = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        print(f"[RAG] Loading embedding model: {EMBED_MODEL}")
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def chunk_text(text: str, source: str, metadata: dict = None) -> list[dict]:
    text = text.strip()
    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]

        if end < len(text):
            last_period = max(chunk.rfind(". "), chunk.rfind(".\n"), chunk.rfind("? "), chunk.rfind("! "))
            if last_period > CHUNK_SIZE // 2:
                chunk = chunk[: last_period + 1]
                end = start + last_period + 1

        chunk = chunk.strip()
        if chunk:
            doc_metadata = {
                "source": source,
                "chunk_index": idx,
                **(metadata or {}),
            }
            chunks.append({
                "id": f"{source}_{idx}",
                "text": chunk,
                "metadata": doc_metadata,
            })
            idx += 1

        start = end - CHUNK_OVERLAP

    return chunks


def ingest_slack(json_path: str) -> int:
    with open(json_path) as f:
        channels = json.load(f)

    all_chunks = []
    for channel in channels:
        channel_name = channel.get("channel", "unknown")
        messages = channel.get("messages", [])

        for i in range(0, len(messages), 5):
            block = messages[i : i + 5]
            text = "\n".join(
                f"[{m.get('user', 'unknown')} in #{channel_name}]: {m.get('text', '')}"
                for m in block
            )
            chunks = chunk_text(
                text,
                source=f"slack_{channel_name}",
                metadata={"type": "slack", "channel": channel_name},
            )
            all_chunks.extend(chunks)

    return _store_chunks(all_chunks)


def ingest_notion(md_path: str) -> int:
    with open(md_path) as f:
        content = f.read()

    sections = re.split(r"\n## ", content)
    all_chunks = []

    for section in sections:
        if not section.strip():
            continue
        first_line = section.split("\n")[0].strip("# ").strip()
        chunks = chunk_text(
            section,
            source=f"notion_{re.sub(r'[^a-z0-9]', '_', first_line.lower()[:40])}",
            metadata={"type": "notion", "section": first_line},
        )
        all_chunks.extend(chunks)

    return _store_chunks(all_chunks)


def ingest_text(text: str, source_name: str, doc_type: str = "manual") -> int:
    chunks = chunk_text(text, source=source_name, metadata={"type": doc_type})
    return _store_chunks(chunks)


def _store_chunks(chunks: list[dict]) -> int:
    if not chunks:
        return 0

    collection = get_collection()
    embedder = get_embedder()

    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, show_progress_bar=False).tolist()

    collection.upsert(
        ids=[c["id"] for c in chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[c["metadata"] for c in chunks],
    )
    print(f"[RAG] Stored {len(chunks)} chunks.")
    return len(chunks)


def retrieve(query: str, top_k: int = TOP_K) -> list[dict]:
    collection = get_collection()
    embedder = get_embedder()

    query_embedding = embedder.encode([query], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "source": meta.get("source", "unknown"),
            "score": round(1 - dist, 3),
            "metadata": meta,
        })

    return chunks


def collection_stats() -> dict:
    collection = get_collection()
    count = collection.count()
    return {"total_chunks": count, "collection": COLLECTION, "chroma_path": CHROMA_PATH}


def reset_collection():
    global _collection
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    _collection = None
    get_collection()
    print("[RAG] Collection reset.")