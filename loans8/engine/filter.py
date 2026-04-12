from __future__ import annotations

from loans8.api.schemas import LoanProduct, PolicyInputs
from loans8.engine.eligibility import PreEligibilityResult


def hard_filter_loans(
    loans: list[LoanProduct],
    policy: PolicyInputs,
    pre_eligibility: PreEligibilityResult,
) -> list[LoanProduct]:
    passing: list[LoanProduct] = []
    for loan in loans:
        e = loan.eligibility
        t = loan.product_terms

        if policy.credit_score < e.min_credit_score:
            continue
        if e.max_credit_score and policy.credit_score > e.max_credit_score:
            continue

        if policy.net_monthly_income < e.min_net_income:
            continue

        if policy.employment_type not in e.allowed_employment_types:
            continue

        max_tenure_for_age = (65 - policy.age) * 12
        if t.min_tenure_months > max_tenure_for_age:
            continue

        if policy.requested_amount < t.min_amount:
            continue

        if e.collateral_required and not policy.collateral_offered:
            continue

        passing.append(loan)
    return passing
