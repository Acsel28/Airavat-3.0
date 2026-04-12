from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class PolicyInputs(BaseModel):
    age: int = Field(..., ge=18, le=80)
    employment_type: str = Field(..., pattern="^(salaried|self_employed|business_owner)$")
    gross_monthly_income: int = Field(..., ge=1)
    net_monthly_income: int = Field(..., ge=1)
    existing_emi_monthly: int = Field(..., ge=0)
    credit_score: int = Field(..., ge=300, le=900)
    fraud_score: int = Field(..., ge=0, le=100)
    risk_persona: str = Field(..., pattern="^(conservative|standard|first_time|distressed)$")
    intent_category: str | None = None
    requested_amount: int = Field(..., ge=1)
    preferred_tenure_months: int | None = None
    collateral_offered: bool = False
    collateral_value: int | None = None
    missed_payments_last_12m: int = Field(..., ge=0)


class OfferRequest(BaseModel):
    session_id: str
    query: str
    loan_choice_index: int | None = None
    policy_inputs: PolicyInputs
    negotiate: bool = False
    negotiation_inputs: list[str] = []


class OfferTerms(BaseModel):
    approved_amount: int
    tenure_months: int
    interest_rate_annual: float
    emi_monthly: int
    processing_fee_pct: float
    processing_fee_amount: int
    total_payable: int


class EligibilitySummary(BaseModel):
    foir_after_loan: float
    foir_gate_passed: bool
    credit_score_gate_passed: bool
    age_tenure_gate_passed: bool
    fraud_gate_passed: bool
    final_decision: str
    rejection_reason: str | None


class GeneratedOffer(BaseModel):
    session_id: str
    loan_id: str
    loan_name: str
    generated_at: str
    offer: OfferTerms
    eligibility_summary: EligibilitySummary


class RoundLog(BaseModel):
    round: int
    user_utterance: str
    user_intent: str
    concession_offered: str | None
    offer_snapshot: OfferTerms


class ConcessionTracker(BaseModel):
    amount_extended_pct: float = 0.0
    rate_discounted_pct: float = 0.0
    fee_waived_pct: float = 0.0
    tenure_extended: bool = False


class NegotiationState(BaseModel):
    session_id: str
    loan_id: str
    rounds_elapsed: int = 0
    max_rounds: int = 8
    status: str = "active"
    hard_limits: dict
    current_offer: OfferTerms
    concession_tracker: ConcessionTracker = ConcessionTracker()
    conversion_probability: float = 0.5
    recommended_next_concession: str | None = None
    round_log: list[RoundLog] = []


class LoanProductEligibility(BaseModel):
    min_credit_score: int
    max_credit_score: int | None
    min_net_income: int
    allowed_employment_types: list[str]
    min_age: int
    max_age_at_maturity: int
    collateral_required: bool


class LoanProductTerms(BaseModel):
    min_amount: int
    max_amount: int
    min_tenure_months: int
    max_tenure_months: int
    base_interest_rate_annual: float
    max_interest_rate_annual: float
    processing_fee_pct: float
    processing_fee_waivable: bool
    moratorium_months_available: int


class LoanProductNegotiationLimits(BaseModel):
    max_rate_discount_pct: float
    max_amount_extension_pct: float
    processing_fee_min_pct: float
    tenure_extension_allowed: bool


class LoanProduct(BaseModel):
    loan_id: str
    loan_name: str
    loan_type: str
    intent_tags: list[str]
    eligibility: LoanProductEligibility
    product_terms: LoanProductTerms
    negotiation_limits: LoanProductNegotiationLimits


class RetrievalInfo(BaseModel):
    method: str
    intent: Optional[str]
    results: list[dict[str, Any]]


class OfferResponse(BaseModel):
    session_id: str
    retrieval: RetrievalInfo
    selected_loan: Optional[dict[str, Any]]
    offer: Optional[GeneratedOffer]
    tts_script: Optional[str]
    audit_trail: list[dict[str, Any]]


class NegotiationTurnRequest(BaseModel):
    session_id: str
    loan: LoanProduct
    policy_inputs: PolicyInputs
    negotiation_state: NegotiationState
    customer_utterance: str


class NegotiationTurnResponse(BaseModel):
    session_id: str
    negotiation_state: NegotiationState
    verbal_response: str
    status: Literal["active", "accepted", "escalated"]
    consent_record: Optional[dict[str, Any]] = None
