from __future__ import annotations

import math
from typing import Optional

from config import (
    CREDIT_BASE,
    CREDIT_FRAUD_PENALTY_MULTIPLIER,
    CREDIT_INCOME_DIVISOR,
    CREDIT_INCOME_WEIGHT,
    CREDIT_NOISE_RANGE,
    CREDIT_SCORE_MAX,
    CREDIT_SCORE_MIN,
    PERSONA_SCORE,
)


def calculate_credit_score(
    verified_income: int,
    declared_income: int,
    existing_emi_monthly: int,
    requested_amount: int,
    requested_tenure_months: Optional[int],
    fraud_score: int,
    risk_persona: str,
    session_id: str,
) -> int:
    tenure: int = requested_tenure_months if requested_tenure_months else 120
    income: int = verified_income if verified_income > 0 else declared_income
    if income <= 0:
        return CREDIT_SCORE_MIN

    r: float = 0.10 / 12
    emi: float = requested_amount * r * (1 + r) ** tenure / ((1 + r) ** tenure - 1)
    emi_ratio: float = existing_emi_monthly / income
    loan_stress: float = emi / income
    gap: float = abs(declared_income - income) / income

    emi_component: int = (
        +40 if emi_ratio < 0.2 else +10 if emi_ratio < 0.4 else -50 if emi_ratio < 0.6 else -120
    )
    stress_component: int = (
        +30 if loan_stress < 0.3 else 0 if loan_stress < 0.5 else -60 if loan_stress < 0.7 else -150
    )
    tenure_component: int = (+20 if tenure >= 180 else 0 if tenure >= 60 else -30)
    gap_component: int = (+20 if gap < 0.1 else 0 if gap < 0.3 else -60)
    noise: int = hash(session_id) % CREDIT_NOISE_RANGE - (CREDIT_NOISE_RANGE // 2)
    persona_adj: int = PERSONA_SCORE.get(risk_persona, 0)

    raw: float = (
        CREDIT_BASE
        + CREDIT_INCOME_WEIGHT * math.log10(1 + income / CREDIT_INCOME_DIVISOR)
        + emi_component
        + stress_component
        + tenure_component
        - CREDIT_FRAUD_PENALTY_MULTIPLIER * fraud_score
        + persona_adj
        + gap_component
        + noise
    )
    return max(CREDIT_SCORE_MIN, min(CREDIT_SCORE_MAX, int(raw)))
