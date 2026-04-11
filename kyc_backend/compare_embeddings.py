import argparse
import ast
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Iterable, List, Optional

import numpy as np
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


DEFAULT_THRESHOLD = 0.92


@dataclass
class KYCEmbedding:
    user_id: int
    email: str
    vector: np.ndarray


@dataclass
class SessionEmbedding:
    session_id: str
    vector: np.ndarray


@dataclass
class MatchResult:
    user_id: int
    email: str
    session_id: str
    similarity: float


def to_float_vector(value) -> np.ndarray:
    """Convert pgvector/text/list payload into a float32 numpy vector."""
    if value is None:
        raise ValueError("Embedding is empty")

    if isinstance(value, np.ndarray):
        arr = value.astype(np.float32)
    elif isinstance(value, (list, tuple)):
        arr = np.asarray(value, dtype=np.float32)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("Embedding string is empty")

        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            pass

        if parsed is None:
            try:
                parsed = ast.literal_eval(raw)
            except Exception:
                # Fallback for pgvector format like: [0.1,0.2,...]
                cleaned = raw.strip("[]")
                parsed = [x for x in cleaned.split(",") if x.strip()]

        arr = np.asarray(parsed, dtype=np.float32)
    else:
        # psycopg/pgvector may return custom objects that are iterable
        if isinstance(value, Iterable):
            arr = np.asarray(list(value), dtype=np.float32)
        else:
            raise ValueError(f"Unsupported embedding type: {type(value)}")

    if arr.ndim != 1:
        raise ValueError(f"Expected 1D embedding, got shape {arr.shape}")
    if arr.size == 0:
        raise ValueError("Embedding has zero length")

    return arr


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        raise ValueError(f"Shape mismatch: {a.shape} vs {b.shape}")

    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


def load_kyc_embeddings(db_url: str, email: Optional[str], user_id: Optional[int]) -> List[KYCEmbedding]:
    engine = create_engine(db_url)

    filters = []
    params = {}
    if email:
        filters.append("email = :email")
        params["email"] = email
    if user_id is not None:
        filters.append("id = :id")
        params["id"] = user_id

    where_clause = ""
    if filters:
        where_clause = " AND " + " AND ".join(filters)

    query = text(
        f"""
        SELECT id, email, embedding
        FROM kyc_users
        WHERE embedding IS NOT NULL {where_clause}
        ORDER BY id
        """
    )

    rows: List[KYCEmbedding] = []
    with engine.connect() as conn:
        for row in conn.execute(query, params):
            vec = to_float_vector(row.embedding)
            rows.append(KYCEmbedding(user_id=row.id, email=row.email, vector=vec))

    return rows


def load_session_embeddings(sqlite_path: str, session_id: Optional[str]) -> List[SessionEmbedding]:
    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Backend DB not found: {sqlite_path}")

    conn = sqlite3.connect(sqlite_path)
    try:
        query = "SELECT session_id, embedding_json FROM authorized_embeddings"
        params = ()
        if session_id:
            query += " WHERE session_id = ?"
            params = (session_id,)

        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    out: List[SessionEmbedding] = []
    for sid, embedding_json in rows:
        vec = to_float_vector(embedding_json)
        out.append(SessionEmbedding(session_id=sid, vector=vec))

    return out


def compare_all(
    kyc_embeddings: List[KYCEmbedding],
    session_embeddings: List[SessionEmbedding],
) -> List[MatchResult]:
    results: List[MatchResult] = []
    for kyc_item in kyc_embeddings:
        for sess_item in session_embeddings:
            sim = cosine_similarity(kyc_item.vector, sess_item.vector)
            results.append(
                MatchResult(
                    user_id=kyc_item.user_id,
                    email=kyc_item.email,
                    session_id=sess_item.session_id,
                    similarity=sim,
                )
            )
    results.sort(key=lambda x: x.similarity, reverse=True)
    return results


def print_summary(results: List[MatchResult], threshold: float, top_k: int) -> None:
    if not results:
        print("No matches to show.")
        return

    print(f"\nTop {min(top_k, len(results))} matches (threshold={threshold:.3f}):")
    for i, r in enumerate(results[:top_k], start=1):
        verdict = "MATCH" if r.similarity >= threshold else "NO_MATCH"
        print(
            f"{i:02d}. user_id={r.user_id} email={r.email} "
            f"session_id={r.session_id} similarity={r.similarity:.6f} -> {verdict}"
        )


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Compare KYC face embeddings with backend session embeddings"
    )
    parser.add_argument("--kyc-db-url", default=os.getenv("NEON_DB_URL"), help="Postgres URL for kyc_users")
    parser.add_argument(
        "--backend-db",
        default=os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "backend", "authorized_embeddings.db")),
        help="Path to backend authorized_embeddings.db",
    )
    parser.add_argument("--email", help="Filter KYC user by email")
    parser.add_argument("--kyc-user-id", type=int, help="Filter KYC user by ID")
    parser.add_argument("--session-id", help="Filter backend session by session_id")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help="Cosine threshold for match")
    parser.add_argument("--top-k", type=int, default=10, help="How many results to print")
    args = parser.parse_args()

    if not args.kyc_db_url:
        raise ValueError("Missing Postgres URL. Set NEON_DB_URL or pass --kyc-db-url")

    kyc_embeddings = load_kyc_embeddings(args.kyc_db_url, args.email, args.kyc_user_id)
    if not kyc_embeddings:
        print("No KYC embeddings found with given filters.")
        return 0

    session_embeddings = load_session_embeddings(args.backend_db, args.session_id)
    if not session_embeddings:
        print("No backend session embeddings found with given filters.")
        return 0

    dim_kyc = kyc_embeddings[0].vector.shape[0]
    dim_session = session_embeddings[0].vector.shape[0]
    if dim_kyc != dim_session:
        print(f"Dimension mismatch: KYC={dim_kyc}, backend={dim_session}")
        return 2

    print(f"Loaded KYC embeddings: {len(kyc_embeddings)}")
    print(f"Loaded backend embeddings: {len(session_embeddings)}")

    results = compare_all(kyc_embeddings, session_embeddings)
    print_summary(results, args.threshold, args.top_k)

    if args.email and args.session_id and results:
        best = results[0]
        verdict = "MATCH" if best.similarity >= args.threshold else "NO_MATCH"
        print(f"\nFinal verdict for requested pair: {verdict}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
