from __future__ import annotations

# ── LLM ──────────────────────────────────────────────────────────────────────
GEMINI_MODEL: str = "gemini-2.5-flash-lite"
LLM_MAX_REQUESTS_PER_MIN: int = 18

# ── Database ─────────────────────────────────────────────────────────────────
DB_PATH: str = "workflow1.db"

# ── Extraction thresholds ─────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD: float = 0.75
MAX_RETRY_TURNS: int = 2

# ── Credit score formula constants ───────────────────────────────────────────
CREDIT_SCORE_MIN: int = 300
CREDIT_SCORE_MAX: int = 900
CREDIT_BASE: int = 520
CREDIT_INCOME_DIVISOR: int = 25000
CREDIT_INCOME_WEIGHT: int = 70
CREDIT_FRAUD_PENALTY_MULTIPLIER: float = 1.2
CREDIT_NOISE_RANGE: int = 41

# ── Persona score adjustments ─────────────────────────────────────────────────
PERSONA_SCORE: dict[str, int] = {
    "conservative_borrower": +30,
    "standard_borrower": 0,
    "first_time_borrower": -15,
    "distressed_borrower": -40,
}

# ── Collateral loan type keywords ─────────────────────────────────────────────
COLLATERAL_LOAN_TYPES: list[str] = [
    "home loan", "home", "house", "flat", "apartment", "property",
    "lap", "loan against property",
    "gold", "jewellery", "ornament",
    "vehicle", "car", "bike", "scooter",
    "business", "equipment", "machinery", "shop",
]

# ── Required fields for completion ───────────────────────────────────────────
REQUIRED_COLLECTED_FIELDS: list[str] = [
    "existing_emi_monthly",
    "active_loan_count",
    "missed_payments_last_12m",
    "collateral_offered",
    "loan_query_free_text",
    "requested_amount",
    "urgency",
]

# ── Optional collected fields ────────────────────────────────────────────────
OPTIONAL_COLLECTED_FIELDS: list[str] = [
    "collateral_type",
    "collateral_value",
    "primary_bank",
    "preferred_tenure_months",
]

# ── Valid risk persona values ─────────────────────────────────────────────────
VALID_PERSONAS: list[str] = [
    "conservative",
    "standard",
    "first_time",
    "distressed",
]
