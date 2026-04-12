from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "tier8.db"

SESSION_DDL = """
CREATE TABLE IF NOT EXISTS loan_sessions (
    session_id TEXT PRIMARY KEY,
    policy_inputs TEXT,
    last_ranked_loans TEXT,
    updated_at TEXT NOT NULL
);
"""


def init_session_store() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SESSION_DDL)
    conn.commit()
    conn.close()


def _upsert_session(session_id: str, policy_inputs: dict | None, last_ranked_loans: list[dict] | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT policy_inputs, last_ranked_loans FROM loan_sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    existing_policy = row[0] if row else None
    existing_ranked = row[1] if row else None

    policy_json = json.dumps(policy_inputs) if policy_inputs is not None else existing_policy
    ranked_json = json.dumps(last_ranked_loans) if last_ranked_loans is not None else existing_ranked

    conn.execute(
        """
        INSERT INTO loan_sessions (session_id, policy_inputs, last_ranked_loans, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            policy_inputs=excluded.policy_inputs,
            last_ranked_loans=excluded.last_ranked_loans,
            updated_at=excluded.updated_at
        """,
        (session_id, policy_json, ranked_json, now),
    )
    conn.commit()
    conn.close()


def save_policy_inputs(session_id: str, policy_inputs: dict) -> None:
    _upsert_session(session_id, policy_inputs, None)


def save_ranked_loans(session_id: str, ranked_loans: list[dict]) -> None:
    _upsert_session(session_id, None, ranked_loans)


def load_policy_inputs(session_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT policy_inputs FROM loan_sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def load_ranked_loans(session_id: str) -> list[dict] | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT last_ranked_loans FROM loan_sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None
