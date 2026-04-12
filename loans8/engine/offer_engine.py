from __future__ import annotations

from datetime import datetime, timezone

from loans8.api.schemas import EligibilitySummary, GeneratedOffer, LoanProduct, OfferTerms, PolicyInputs
from loans8.engine.eligibility import PreEligibilityResult


def generate_offer(
    *,
    loan: LoanProduct,
    policy: PolicyInputs,
    pre_eligibility: PreEligibilityResult,
    session_id: str,
) -> GeneratedOffer:
    t = loan.product_terms

    approved_amount = min(
        policy.requested_amount,
        t.max_amount,
        pre_eligibility.max_eligible_amount_approx,
    )
    approved_amount = max(approved_amount, t.min_amount)

    max_tenure_for_age = (65 - policy.age) * 12
    preferred = policy.preferred_tenure_months or t.max_tenure_months
    tenure_months = min(preferred, t.max_tenure_months, max_tenure_for_age)
    tenure_months = max(tenure_months, t.min_tenure_months)

    spread = 0.0
    if policy.credit_score >= 750:
        spread = 0.0
    elif policy.credit_score >= 650:
        spread = 0.5
    else:
        spread = 1.5
    if policy.risk_persona == "distressed":
        spread += 0.5

    rate_annual = min(t.base_interest_rate_annual + spread, t.max_interest_rate_annual)

    r = rate_annual / 12 / 100
    n = tenure_months
    if r == 0:
        emi = approved_amount // n
    else:
        emi = int(approved_amount * r * (1 + r) ** n / ((1 + r) ** n - 1))

    foir_after = (policy.existing_emi_monthly + emi) / policy.net_monthly_income

    fee_amount = int(approved_amount * t.processing_fee_pct / 100)
    total_payable = emi * tenure_months + fee_amount

    foir_passed = foir_after <= 0.55
    credit_passed = policy.credit_score >= loan.eligibility.min_credit_score
    age_tenure_passed = (policy.age * 12 + tenure_months) <= (65 * 12)
    fraud_passed = policy.fraud_score <= 70

    all_passed = foir_passed and credit_passed and age_tenure_passed and fraud_passed
    decision = "approved" if all_passed else "referred"
    rejection_reason = None
    if not foir_passed:
        rejection_reason = f"FOIR after loan would be {foir_after:.2f}, exceeding 55% limit."
    elif not fraud_passed:
        rejection_reason = f"Fraud score {policy.fraud_score} is too high."

    return GeneratedOffer(
        session_id=session_id,
        loan_id=loan.loan_id,
        loan_name=loan.loan_name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        offer=OfferTerms(
            approved_amount=approved_amount,
            tenure_months=tenure_months,
            interest_rate_annual=rate_annual,
            emi_monthly=emi,
            processing_fee_pct=t.processing_fee_pct,
            processing_fee_amount=fee_amount,
            total_payable=total_payable,
        ),
        eligibility_summary=EligibilitySummary(
            foir_after_loan=foir_after,
            foir_gate_passed=foir_passed,
            credit_score_gate_passed=credit_passed,
            age_tenure_gate_passed=age_tenure_passed,
            fraud_gate_passed=fraud_passed,
            final_decision=decision,
            rejection_reason=rejection_reason,
        ),
    )
