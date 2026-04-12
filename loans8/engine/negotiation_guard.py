from __future__ import annotations

from loans8.api.schemas import LoanProduct, OfferTerms, PolicyInputs


class NegotiationGuard:
    def __init__(self, loan: LoanProduct, initial_offer: OfferTerms, policy: PolicyInputs):
        nl = loan.negotiation_limits
        self.max_amount = int(initial_offer.approved_amount * (1 + nl.max_amount_extension_pct / 100))
        self.min_rate = initial_offer.interest_rate_annual - nl.max_rate_discount_pct
        self.min_rate = max(self.min_rate, loan.product_terms.base_interest_rate_annual - nl.max_rate_discount_pct)
        self.min_processing_fee_pct = nl.processing_fee_min_pct
        self.max_tenure = loan.product_terms.max_tenure_months
        self.max_foir = 0.55
        self.net_income = policy.net_monthly_income
        self.existing_emi = policy.existing_emi_monthly
        self.initial_offer = initial_offer

    def propose(
        self,
        proposed_amount: int | None = None,
        proposed_rate: float | None = None,
        proposed_tenure: int | None = None,
        proposed_fee_pct: float | None = None,
    ) -> dict:
        violations: list[str] = []

        amount = proposed_amount or self.initial_offer.approved_amount
        rate = proposed_rate or self.initial_offer.interest_rate_annual
        tenure = proposed_tenure or self.initial_offer.tenure_months
        fee_pct = proposed_fee_pct if proposed_fee_pct is not None else self.initial_offer.processing_fee_pct

        if amount > self.max_amount:
            amount = self.max_amount
            violations.append(f"Amount clamped to maximum {self.max_amount}")

        if rate < self.min_rate:
            rate = self.min_rate
            violations.append(f"Rate clamped to floor {self.min_rate:.2f}%")

        if tenure > self.max_tenure:
            tenure = self.max_tenure
            violations.append(f"Tenure clamped to maximum {self.max_tenure} months")

        if fee_pct < self.min_processing_fee_pct:
            fee_pct = self.min_processing_fee_pct
            violations.append(f"Processing fee clamped to minimum {self.min_processing_fee_pct}%")

        r = rate / 12 / 100
        n = tenure
        if r == 0:
            emi = amount // n
        else:
            emi = int(amount * r * (1 + r) ** n / ((1 + r) ** n - 1))

        foir = (self.existing_emi + emi) / self.net_income
        if foir > self.max_foir:
            violations.append(
                f"Resulting FOIR {foir:.2f} exceeds 55% limit. Cannot offer this combination."
            )
            return {"allowed": False, "reason": "; ".join(violations), "clamped_values": {}}

        return {
            "allowed": True,
            "reason": "; ".join(violations) if violations else "OK",
            "clamped_values": {
                "approved_amount": amount,
                "interest_rate_annual": rate,
                "tenure_months": tenure,
                "processing_fee_pct": fee_pct,
                "emi_monthly": emi,
                "foir_after": foir,
            },
        }
