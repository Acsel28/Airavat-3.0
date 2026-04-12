from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class FieldConfidence(BaseModel):
    existing_emi_monthly: float = 0.0
    active_loan_count: float = 0.0
    missed_payments_last_12m: float = 0.0
    collateral_offered: float = 0.0
    collateral_type: float = 0.0
    collateral_value: float = 0.0
    primary_bank: float = 0.0
    loan_query_free_text: float = 0.0
    requested_amount: float = 0.0
    preferred_tenure_months: float = 0.0
    urgency: float = 0.0


class LowConfidenceFlags(BaseModel):
    fields: List[str] = Field(default_factory=list)


class LLMExtractionOutput(BaseModel):
    extracted_fields: Dict[str, Any]
    confidence_scores: Dict[str, float]


class LLMInferenceOutput(BaseModel):
    intent_category: Optional[str]
    intent_confidence: Optional[float]
    risk_persona: Optional[str]
    transcript_contradiction_flag: bool = False
    reasoning: Optional[str] = None


class AgentState(TypedDict):
    session_id: str

    # Section 1 - pre_phase1
    full_name: str
    dob: str
    age: int
    gender: str | None
    pan: str
    city: str
    state: str
    kyc_verified: bool
    employer_name: str
    employment_type: str
    gross_monthly_income: int
    net_monthly_income: int
    pf_deducted: bool

    # Section 2 - agent_collected
    existing_emi_monthly: int | None
    active_loan_count: int | None
    missed_payments_last_12m: int | None
    collateral_offered: bool | None
    collateral_type: str | None
    collateral_value: int | None
    primary_bank: str | None
    loan_query_free_text: str | None
    requested_amount: int | None
    preferred_tenure_months: int | None
    urgency: str | None

    # Section 3 - agent_inferred
    intent_category: str | None
    intent_confidence: float | None
    risk_persona: str | None
    transcript_contradiction_flag: bool

    # Section 4 - computed
    credit_score: int | None
    fraud_score: int | None
    foir_current: float | None
    max_eligible_emi: int | None
    max_eligible_amount_approx: int | None

    field_confidence: dict
    low_confidence_flags: list[str]
    pending_clarifications: list[str]

    liveness_passed: bool
    age_kyc_delta: int
    consent_data_collection: str | None
    consent_bureau_pull: str | None
    phase1_completed_at: str | None

    messages: list[dict]
    turn_count: int
    turn_number: int
    phase1_complete: bool
    stage: str
    warmup_turns_done: int
    retry_counts: dict


class PolicyInputs(BaseModel):
    age: int
    employment_type: str
    gross_monthly_income: int
    net_monthly_income: int
    existing_emi_monthly: int
    credit_score: int
    fraud_score: int
    risk_persona: str
    intent_category: str | None
    requested_amount: int
    preferred_tenure_months: int | None
    collateral_offered: bool
    collateral_value: int | None
    missed_payments_last_12m: int


class Phase1Output(BaseModel):
    session_id: str
    query: str
    policy_inputs: PolicyInputs
