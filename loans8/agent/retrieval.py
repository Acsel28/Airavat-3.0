"""Hybrid retrieval: Chroma semantic + SQLite keyword lookup."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import chromadb
from loans8.engine.gemini_embeddings import embed_texts

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "tier8.db"
CHROMA_PATH = BASE_DIR / "chroma_store"
COLLECTION_NAME = "loan_catalog"

INTENT_KEYWORDS = {
    "home_purchase": ["house", "home", "property", "flat", "apartment", "plot", "construction"],
    "home_improvement": ["renovation", "improvement", "repair", "interiors"],
    "vehicle": ["car", "bike", "vehicle", "scooter", "motorcycle", "auto"],
    "personal": ["personal", "wedding", "travel", "emergency", "expense"],
    "medical": ["medical", "hospital", "surgery", "treatment"],
    "education": ["education", "college", "university", "abroad", "studies", "fees", "course"],
    "business": ["business", "shop", "startup", "msme", "machinery", "equipment", "working capital"],
    "debt_consolidation": ["debt", "consolidation", "credit card", "balance transfer"],
}


def _load_all_loans() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM loans").fetchall()
    finally:
        conn.close()

    loans = []
    for row in rows:
        loan = dict(row)
        loan["intent_tags"] = json.loads(loan["intent_tags"])
        loan["use_case_tags"] = json.loads(loan["use_case_tags"])
        loan["eligibility"] = json.loads(loan["eligibility"])
        loan["product_terms"] = json.loads(loan["product_terms"])
        loan["negotiation_limits"] = json.loads(loan["negotiation_limits"])
        loans.append(loan)
    return loans


def get_loans_by_intent(intent: str, top_k: int = 3) -> list[dict]:
    loans = [l for l in _load_all_loans() if intent in l.get("intent_tags", [])][:top_k]
    for loan in loans:
        loan["match_score"] = 1.0
        loan["match_source"] = "keyword"
    return loans


def classify_intent(query: str) -> str | None:
    text = query.lower()
    for intent, words in INTENT_KEYWORDS.items():
        hits = sum(1 for w in words if w in text)
        if hits >= 2:
            return intent
    return None


def _semantic_search(query: str, top_k: int) -> dict[str, float]:
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    collection = client.get_collection(name=COLLECTION_NAME)
    query_embedding = embed_texts([query], kind="query")[0]
    result = collection.query(query_embeddings=[query_embedding], n_results=top_k)

    semantic_scores: dict[str, float] = {}
    ids = result.get("ids", [[]])[0]
    distances = result.get("distances", [[]])[0]

    for loan_id, distance in zip(ids, distances):
        semantic_scores[loan_id] = 1 - float(distance)
    return semantic_scores


def _keyword_scores(query: str) -> dict[str, float]:
    tokens = [word.lower() for word in query.split() if len(word) > 3]
    if not tokens:
        return {}

    scores: dict[str, float] = {}
    for loan in _load_all_loans():
        haystack = f"{loan['use_case_description']} {' '.join(loan['use_case_tags'])}".lower()
        hits = sum(1 for token in tokens if token in haystack)
        if hits > 0:
            scores[loan["loan_id"]] = hits / len(tokens)
    return scores


def retrieve_loan(query: str, top_k: int = 3) -> list[dict]:
    """Return ranked list of loan records using hybrid retrieval."""
    semantic = _semantic_search(query, top_k)
    keyword = _keyword_scores(query)
    loans_by_id = {loan["loan_id"]: loan for loan in _load_all_loans()}

    combined: dict[str, dict] = {}
    for loan_id, sem_score in semantic.items():
        key_score = keyword.get(loan_id, 0.0)
        final_score = sem_score + 0.3 * key_score
        source = "both" if loan_id in keyword else "semantic"
        combined[loan_id] = {
            "final_score": final_score,
            "match_source": source,
            "semantic_score": sem_score,
            "keyword_score": key_score,
        }

    for loan_id, key_score in keyword.items():
        if loan_id in combined:
            continue
        combined[loan_id] = {
            "final_score": 0.3 * key_score,
            "match_source": "keyword",
            "semantic_score": 0.0,
            "keyword_score": key_score,
        }

    ranked_ids = sorted(combined, key=lambda lid: combined[lid]["final_score"], reverse=True)[:top_k]
    results = []
    for loan_id in ranked_ids:
        if loan_id not in loans_by_id:
            continue
        loan = dict(loans_by_id[loan_id])
        loan["match_score"] = round(combined[loan_id]["final_score"], 4)
        loan["match_source"] = combined[loan_id]["match_source"]
        results.append(loan)
    return results


def get_loan_recommendations(query: str, top_k: int = 3) -> dict:
    """Return intent + retrieval method + ranked results."""
    intent = classify_intent(query)
    if intent:
        results = get_loans_by_intent(intent, top_k=top_k)
        return {"intent": intent, "retrieval_method": "keyword_shortcut", "results": results}

    results = retrieve_loan(query, top_k=top_k)
    return {"intent": None, "retrieval_method": "hybrid_rag", "results": results}
