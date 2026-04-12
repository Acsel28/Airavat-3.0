"""Audit event emitter and session trail fetcher."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "tier8.db"


def emit_audit_event(
    session_id: str,
    event_type: str,
    loan_id: str,
    terms_snapshot: dict,
    customer_utterance: str = "",
    agent_action: str = "",
    round_number: int = 0,
    metadata: dict | None = None,
) -> str:
    """Insert one audit event and return event_id."""
    event_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO audit_events VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            event_id,
            session_id,
            event_type,
            round_number,
            loan_id,
            json.dumps(terms_snapshot),
            customer_utterance,
            agent_action,
            json.dumps(metadata or {}),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return event_id


def get_session_audit_trail(session_id: str) -> list[dict]:
    """Return all audit events for a session ordered by timestamp."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT * FROM audit_events WHERE session_id=? ORDER BY timestamp ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    columns = [
        "event_id",
        "session_id",
        "event_type",
        "round_number",
        "loan_id",
        "terms_snapshot",
        "customer_utterance",
        "agent_action",
        "metadata",
        "timestamp",
    ]
    return [dict(zip(columns, row)) for row in rows]
