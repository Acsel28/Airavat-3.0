from __future__ import annotations

from loans8.api.schemas import LoanProduct, PolicyInputs


def rerank_loans(loans: list[LoanProduct], policy: PolicyInputs) -> list[LoanProduct]:
    def score(loan: LoanProduct) -> float:
        intent_match = 1.0 if policy.intent_category in loan.intent_tags else 0.0

        e = loan.eligibility
        score_range = (e.max_credit_score or 900) - e.min_credit_score
        if score_range > 0:
            credit_fit = 1.0 - abs(policy.credit_score - (e.min_credit_score + score_range / 2)) / score_range
            credit_fit = max(0.0, min(1.0, credit_fit))
        else:
            credit_fit = 1.0

        base_rate = loan.product_terms.base_interest_rate_annual
        rate_score = 1.0 / (1.0 + base_rate / 10.0)

        collateral_score = 1.0 if (loan.eligibility.collateral_required == policy.collateral_offered) else 0.5

        return (
            intent_match * 0.40
            + credit_fit * 0.30
            + rate_score * 0.20
            + collateral_score * 0.10
        )

    return sorted(loans, key=score, reverse=True)[:3]
