"""SQLite setup for Tier 8."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data.loans import LOAN_CATALOG

DB_PATH = BASE_DIR / "tier8.db"


LOANS_DDL = """
CREATE TABLE IF NOT EXISTS loans (
    loan_id TEXT PRIMARY KEY,
    loan_name TEXT,
    loan_type TEXT,
    intent_tags TEXT,
    use_case_description TEXT,
    use_case_tags TEXT,
    eligibility TEXT,
    product_terms TEXT,
    negotiation_limits TEXT
);
"""

AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    round_number INTEGER,
    loan_id TEXT,
    terms_snapshot TEXT,
    customer_utterance TEXT,
    agent_action TEXT,
    metadata TEXT,
    timestamp TEXT NOT NULL
);
"""

INSERT_SQL = """
INSERT OR REPLACE INTO loans (
    loan_id, loan_name, loan_type, intent_tags, use_case_description,
    use_case_tags, eligibility, product_terms, negotiation_limits
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def setup_sqlite() -> None:
    """Create DB schema and upsert all loan records."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DROP TABLE IF EXISTS loans")
        conn.execute(LOANS_DDL)
        conn.execute(AUDIT_DDL)

        for loan in LOAN_CATALOG:
            conn.execute(
                INSERT_SQL,
                (
                    loan["loan_id"],
                    loan["loan_name"],
                    loan["loan_type"],
                    json.dumps(loan["intent_tags"]),
                    loan["use_case_description"],
                    json.dumps(loan["use_case_tags"]),
                    json.dumps(loan["eligibility"]),
                    json.dumps(loan["product_terms"]),
                    json.dumps(loan["negotiation_limits"]),
                ),
            )

        conn.commit()
    finally:
        conn.close()

    print("SQLite setup complete. 18 loans inserted.")


if __name__ == "__main__":
    setup_sqlite()
