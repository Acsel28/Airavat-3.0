from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from workflow1.agent.prompts import (
    AUDIT_AGENT_TEMPLATE,
    AUDIT_HANDOFF_AGENT_SAID,
    AUDIT_HEADER,
    AUDIT_LINE_TEMPLATE,
    AUDIT_USER_TEMPLATE,
    DB_READY_TEMPLATE,
)
from workflow1.config import DB_PATH


def setup_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wf1_audit (
            event_id    TEXT PRIMARY KEY,
            session_id  TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            phase       TEXT,
            fields_snap TEXT,
            agent_said  TEXT,
            user_said   TEXT,
            timestamp   TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()
    print(DB_READY_TEMPLATE.format(db_path=DB_PATH))


def log_turn(session_id: str, phase: str, fields_snap: dict, agent_said: str, user_said: str) -> None:
    snapshot = dict(fields_snap)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO wf1_audit VALUES (?,?,?,?,?,?,?,?)",
        (
            str(uuid.uuid4()),
            session_id,
            "TURN",
            phase,
            json.dumps(snapshot),
            agent_said,
            user_said,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def log_handoff(session_id: str, handoff_payload: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO wf1_audit VALUES (?,?,?,?,?,?,?,?)",
        (
            str(uuid.uuid4()),
            session_id,
            "HANDOFF",
            "done",
            json.dumps(handoff_payload),
            AUDIT_HANDOFF_AGENT_SAID,
            "",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def print_audit_trail(session_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT event_type, phase, agent_said, user_said, timestamp "
        "FROM wf1_audit WHERE session_id=? ORDER BY timestamp ASC",
        (session_id,),
    ).fetchall()
    conn.close()

    print(AUDIT_HEADER)
    for row in rows:
        print(AUDIT_LINE_TEMPLATE.format(timestamp=row[4], event_type=row[0], phase=row[1]))
        if row[3]:
            print(AUDIT_USER_TEMPLATE.format(text=row[3][:80]))
        print(AUDIT_AGENT_TEMPLATE.format(text=row[2][:80]))
