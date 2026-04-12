from __future__ import annotations

from pydantic import BaseModel

from loans8.api.schemas import PolicyInputs


class PreEligibilityResult(BaseModel):
    passed: bool
    rejection_reason: str | None
    foir_current: float
    max_eligible_emi: int
    max_eligible_amount_approx: int
    age_warning: bool


def run_pre_eligibility_gate(policy: PolicyInputs) -> PreEligibilityResult:
    foir_current = policy.existing_emi_monthly / policy.net_monthly_income

    if foir_current >= 0.55:
        return PreEligibilityResult(
            passed=False,
            rejection_reason=(
                f"Existing FOIR {foir_current:.2f} already at or above 55% limit. "
                "No EMI headroom available."
            ),
            foir_current=foir_current,
            max_eligible_emi=0,
            max_eligible_amount_approx=0,
            age_warning=policy.age > 58,
        )

    if policy.fraud_score > 70:
        return PreEligibilityResult(
            passed=False,
            rejection_reason=f"Fraud score {policy.fraud_score} exceeds threshold of 70.",
            foir_current=foir_current,
            max_eligible_emi=0,
            max_eligible_amount_approx=0,
            age_warning=policy.age > 58,
        )

    max_eligible_emi = int(policy.net_monthly_income * 0.55) - policy.existing_emi_monthly
    r = 0.01
    n = 120
    max_eligible_amount_approx = int(max_eligible_emi * ((1 + r) ** n - 1) / (r * (1 + r) ** n))

    return PreEligibilityResult(
        passed=True,
        rejection_reason=None,
        foir_current=foir_current,
        max_eligible_emi=max_eligible_emi,
        max_eligible_amount_approx=max_eligible_amount_approx,
        age_warning=policy.age > 58,
    )
