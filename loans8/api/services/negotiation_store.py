from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "tier8.db"

NEGOTIATION_DDL = """
CREATE TABLE IF NOT EXISTS negotiation_sessions (
    negotiation_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    loan_id TEXT NOT NULL,
    negotiation_state TEXT NOT NULL,
    initial_offer TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_negotiation_store() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(NEGOTIATION_DDL)
    conn.commit()
    conn.close()


def save_negotiation_state(
    *,
    negotiation_id: str,
    session_id: str,
    loan_id: str,
    negotiation_state: dict,
    initial_offer: dict,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO negotiation_sessions (
            negotiation_id, session_id, loan_id, negotiation_state, initial_offer, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(negotiation_id) DO UPDATE SET
            negotiation_state=excluded.negotiation_state,
            initial_offer=excluded.initial_offer,
            updated_at=excluded.updated_at
        """,
        (
            negotiation_id,
            session_id,
            loan_id,
            json.dumps(negotiation_state),
            json.dumps(initial_offer),
            now,
        ),
    )
    conn.commit()
    conn.close()


def load_negotiation_state(negotiation_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT session_id, loan_id, negotiation_state, initial_offer FROM negotiation_sessions WHERE negotiation_id=?",
        (negotiation_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return {
            "session_id": row[0],
            "loan_id": row[1],
            "negotiation_state": json.loads(row[2]),
            "initial_offer": json.loads(row[3]),
        }
    except Exception:
        return None
