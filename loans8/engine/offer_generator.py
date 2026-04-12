"""Deterministic loan offer generator (no LLM)."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "tier8.db"


def _load_loan(loan_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM loans WHERE loan_id=?", (loan_id,)).fetchone()
    finally:
        conn.close()

    if not row:
        return None

    loan = dict(row)
    loan["use_case_tags"] = json.loads(loan["use_case_tags"])
    loan["negotiable"] = json.loads(loan["negotiable"])
    loan["non_negotiable"] = json.loads(loan["non_negotiable"])
    loan["collateral_required"] = bool(loan["collateral_required"])
    return loan


def _compute_emi(amount: float, annual_rate_pct: float, tenure_months: int) -> int:
    if amount <= 0 or tenure_months <= 0:
        return 0
    monthly_rate = annual_rate_pct / 100 / 12
    if monthly_rate == 0:
        return int(round(amount / tenure_months))
    growth = (1 + monthly_rate) ** tenure_months
    emi = amount * monthly_rate * growth / (growth - 1)
    return int(round(emi))


def _select_tenure(loan: dict, requested_tenure_months: int | None) -> int:
    options = loan["negotiable"]["tenure_options_months"]
    if requested_tenure_months in options:
        return requested_tenure_months

    if requested_tenure_months is None:
        return options[len(options) // 2]

    return min(options, key=lambda t: abs(t - requested_tenure_months))


def _compute_rate(loan: dict, credit_score: int, risk_persona: str) -> float:
    base_rate = float(loan["base_rate"])
    max_rate = float(loan["max_rate"])

    if credit_score >= 800:
        rate = base_rate
    elif credit_score >= 750:
        rate = base_rate + 0.25
    elif credit_score >= 700:
        rate = base_rate + 0.75
    else:
        rate = base_rate + 1.50

    if risk_persona == "distressed_borrower":
        rate += 0.50
    elif risk_persona == "first_time_borrower":
        rate += 0.25

    return round(min(rate, max_rate), 2)


def _empty_rejection(loan_id: str, subtype: str, reason: str) -> dict:
    return {
        "loan_id": loan_id,
        "subtype": subtype,
        "eligible_amount": 0,
        "rate_pct": 0.0,
        "tenure_months": 0,
        "emi_monthly": 0,
        "processing_fee_inr": 0,
        "foir_used": 0.0,
        "eligibility_status": "rejected",
        "rejection_reason": reason,
        "negotiation_envelope": {
            "max_amount_allowed": 0,
            "min_rate_allowed": 0.0,
            "rate_reduction_eligible": False,
            "tenure_options_months": [],
        },
        "non_negotiable": [],
    }


def generate_offer(policy_inputs: dict) -> dict:
    loan_id = policy_inputs["loan_id"]
    loan = _load_loan(loan_id)

    if not loan:
        return _empty_rejection(loan_id, "Unknown", "loan_not_found")

    credit_score = int(policy_inputs["credit_score"])
    fraud_score = int(policy_inputs["fraud_score"])
    declared_income_monthly = int(policy_inputs["declared_income_monthly"])
    existing_emi_monthly = int(policy_inputs["existing_emi_monthly"])
    risk_persona = policy_inputs["risk_persona"]
    requested_amount = int(policy_inputs["requested_amount"])
    collateral_value = policy_inputs.get("collateral_value")
    requested_tenure = policy_inputs.get("requested_tenure_months")

    if credit_score < int(loan["min_credit_score"]):
        return _empty_rejection(loan_id, loan["subtype"], "credit_score_below_minimum")
    if fraud_score > 40:
        return _empty_rejection(loan_id, loan["subtype"], "fraud_score_above_cutoff")
    if declared_income_monthly <= 0:
        return _empty_rejection(loan_id, loan["subtype"], "invalid_income")

    tenure_options = loan["negotiable"]["tenure_options_months"]
    selected_tenure = _select_tenure(loan, requested_tenure)
    mid_tenure = tenure_options[len(tenure_options) // 2]
    max_foir = float(loan["max_foir"])

    def compute_income_eligible(tenure_months: int) -> float:
        surplus_income = max(0.0, declared_income_monthly - existing_emi_monthly)
        return surplus_income * max_foir * tenure_months

    def clamp_amount(income_eligible_amount: float) -> float:
        bounds = [requested_amount, income_eligible_amount, float(loan["max_amount"])]
        if loan["collateral_required"]:
            collateral_eligible = 0.0
            if collateral_value is not None and loan["ltv_cap"] is not None:
                collateral_eligible = float(collateral_value) * float(loan["ltv_cap"])
            bounds.append(collateral_eligible)
        amount = min(bounds)
        return max(amount, float(loan["min_amount"]))

    first_pass_income_eligible = compute_income_eligible(mid_tenure)
    _ = clamp_amount(first_pass_income_eligible)

    final_income_eligible = compute_income_eligible(selected_tenure)
    eligible_amount = clamp_amount(final_income_eligible)

    rate = _compute_rate(loan, credit_score, risk_persona)
    emi = _compute_emi(eligible_amount, rate, selected_tenure)

    # FOIR compliance: reduce amount with bounded binary search if required.
    low = 0
    high = int(eligible_amount)
    foir = (existing_emi_monthly + emi) / declared_income_monthly
    if foir > max_foir:
        for _ in range(20):
            mid = (low + high) // 2
            test_emi = _compute_emi(mid, rate, selected_tenure)
            test_foir = (existing_emi_monthly + test_emi) / declared_income_monthly
            if test_foir <= max_foir:
                low = mid
            else:
                high = mid
        eligible_amount = max(float(loan["min_amount"]), float(low))
        emi = _compute_emi(eligible_amount, rate, selected_tenure)
        foir = (existing_emi_monthly + emi) / declared_income_monthly

    if foir > max_foir:
        return _empty_rejection(loan_id, loan["subtype"], "foir_above_policy_limit")

    processing_fee = max(
        eligible_amount * float(loan["processing_fee_pct"]) / 100,
        float(loan["processing_fee_floor_inr"]),
    )

    rate_cond = loan["negotiable"]["rate_reduction_condition"]
    rate_reduction_eligible = (
        credit_score >= int(rate_cond["min_credit_score"])
        and fraud_score <= int(rate_cond["max_fraud_score"])
    )

    reduction_bps = float(loan["negotiable"]["rate_reduction_bps_max"]) / 100
    min_rate_allowed = rate - reduction_bps if rate_reduction_eligible else rate

    return {
        "loan_id": loan["loan_id"],
        "subtype": loan["subtype"],
        "eligible_amount": int(round(eligible_amount)),
        "rate_pct": round(rate, 2),
        "tenure_months": int(selected_tenure),
        "emi_monthly": int(emi),
        "processing_fee_inr": int(round(processing_fee)),
        "foir_used": round(float(foir), 4),
        "eligibility_status": "approved",
        "rejection_reason": None,
        "negotiation_envelope": {
            "max_amount_allowed": int(round(eligible_amount * (1 + loan["negotiable"]["amount_delta_pct"]))),
            "min_rate_allowed": round(min_rate_allowed, 2),
            "rate_reduction_eligible": bool(rate_reduction_eligible),
            "tenure_options_months": list(loan["negotiable"]["tenure_options_months"]),
        },
        "non_negotiable": list(loan["non_negotiable"]),
    }
