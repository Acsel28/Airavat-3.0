from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from config import DB_PATH

SESSIONS_DDL = """
CREATE TABLE IF NOT EXISTS wf1_sessions (
    session_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def init_sessions_table() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SESSIONS_DDL)
    conn.commit()
    conn.close()


def save_state(session_id: str, state: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(state)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO wf1_sessions (session_id, state_json, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            state_json=excluded.state_json,
            updated_at=excluded.updated_at
        """,
        (session_id, payload, now, now),
    )
    conn.commit()
    conn.close()


def load_state(session_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT state_json FROM wf1_sessions WHERE session_id=?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None
