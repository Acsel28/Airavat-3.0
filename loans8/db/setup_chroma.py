"""ChromaDB setup for Tier 8."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import chromadb

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data.loans import LOAN_CATALOG
from loans8.engine.gemini_embeddings import MODEL_NAME, embed_texts

CHROMA_PATH = BASE_DIR / "chroma_store"
COLLECTION_NAME = "loan_catalog"


def _flatten_metadata(record: dict) -> dict:
    meta: dict = {}
    for key, value in record.items():
        if isinstance(value, (dict, list)):
            meta[key] = json.dumps(value)
        elif value is None:
            meta[key] = "null"
        else:
            meta[key] = value
    return meta


def _needs_rebuild(collection) -> bool:
    current = collection.get(include=["metadatas"])
    ids = current.get("ids", []) or []
    unique_ids = set(ids)
    expected_ids = {loan["loan_id"] for loan in LOAN_CATALOG}
    if unique_ids != expected_ids:
        return True

    metadatas = current.get("metadatas", []) or []
    first_meta = metadatas[0] if metadatas else {}
    return (first_meta or {}).get("embedding_provider") != MODEL_NAME


def setup_chroma() -> None:
    """Create and embed loan catalog in Chroma using Gemini API embeddings."""
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    if not _needs_rebuild(collection):
        print("ChromaDB setup skipped. 18 documents already embedded.")
        return

    ids = []
    docs = []
    metas = []

    for loan in LOAN_CATALOG:
        ids.append(loan["loan_id"])
        docs.append(f"{loan['use_case_description']} {' '.join(loan['use_case_tags'])}")
        meta = _flatten_metadata(loan)
        meta["embedding_provider"] = MODEL_NAME
        metas.append(meta)

    embeddings = embed_texts(docs, kind="document")

    # Recreate only after embeddings are ready, so failures never wipe existing data.
    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
    print("ChromaDB setup complete. 18 documents embedded.")


if __name__ == "__main__":
    setup_chroma()
