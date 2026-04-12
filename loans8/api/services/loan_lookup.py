from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from loans8.api.schemas import LoanProduct

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "tier8.db"


def get_loan_by_id(loan_id: str) -> LoanProduct | None:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT loan_id, loan_name, loan_type, intent_tags, eligibility, product_terms, negotiation_limits "
        "FROM loans WHERE loan_id=?",
        (loan_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None

    try:
        loan = {
            "loan_id": row[0],
            "loan_name": row[1],
            "loan_type": row[2],
            "intent_tags": json.loads(row[3]) if row[3] else [],
            "eligibility": json.loads(row[4]) if row[4] else {},
            "product_terms": json.loads(row[5]) if row[5] else {},
            "negotiation_limits": json.loads(row[6]) if row[6] else {},
        }
        return LoanProduct.model_validate(loan)
    except Exception:
        return None
