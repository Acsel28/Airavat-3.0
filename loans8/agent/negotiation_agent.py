from __future__ import annotations

import json
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph

from loans8.agent.prompts import (
    ACCEPTANCE_PROMPT,
    ESCALATION_PROMPT,
    NEGOTIATION_SYSTEM_PROMPT,
    NEGOTIATION_TURN_PROMPT,
    OFFER_PRESENTATION_PROMPT,
)
from loans8.api.schemas import ConcessionTracker, LoanProduct, NegotiationState, OfferTerms, PolicyInputs, RoundLog
from loans8.engine.consent import capture_consent_event
from loans8.engine.conversion import compute_concession_increment, compute_conversion_probability, recommend_concession
from loans8.engine.negotiation_guard import NegotiationGuard
from loans8.engine.rate_limit import RequestRateLimiter

_NEGOTIATION_RATE_LIMITER: RequestRateLimiter | None = None


def _get_negotiation_rate_limiter() -> RequestRateLimiter:
    global _NEGOTIATION_RATE_LIMITER
    if _NEGOTIATION_RATE_LIMITER is not None:
        return _NEGOTIATION_RATE_LIMITER
    max_per_min = int(os.getenv("NEGOTIATION_API_MAX_REQUESTS_PER_MIN", "12"))
    _NEGOTIATION_RATE_LIMITER = RequestRateLimiter(max_requests=max_per_min, window_seconds=60)
    return _NEGOTIATION_RATE_LIMITER


def _llm_text(prompt: str) -> str:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
    _get_negotiation_rate_limiter().acquire()
    full_prompt = f"{NEGOTIATION_SYSTEM_PROMPT}\n\n{prompt}"
    response = llm.invoke(full_prompt)
    content = response.content if isinstance(response.content, str) else str(response.content)
    return content.strip()


def _split_intent_block(text: str) -> tuple[str, str]:
    if "INTENT:" not in text:
        return text.strip(), "rejecting"
    spoken, intent_block = text.split("INTENT:", 1)
    intent_block = intent_block.strip()
    start = intent_block.find("{")
    end = intent_block.rfind("}")
    intent = "rejecting"
    if start >= 0 and end >= start:
        try:
            payload = json.loads(intent_block[start : end + 1])
            intent = payload.get("user_intent") or "rejecting"
        except Exception:
            intent = "rejecting"
    return spoken.strip(), intent


def _format_concession_description(lever: str | None, increment: float, offer: OfferTerms) -> str:
    if not lever or lever == "hold":
        return "hold"
    if lever == "amount":
        return f"EMI reduced — new amount ₹{offer.approved_amount} at ₹{offer.emi_monthly}/month"
    if lever == "rate":
        return f"Rate reduced by {increment:.2f}% — new EMI ₹{offer.emi_monthly}"
    if lever == "fee":
        return f"Processing fee reduced by {int(increment)}%"
    if lever == "tenure":
        return f"Tenure extended by 24 months — new EMI ₹{offer.emi_monthly}"
    return "hold"


def _apply_concession(
    offer: OfferTerms,
    lever: str,
    increment: float,
    tracker: ConcessionTracker,
) -> tuple[OfferTerms, ConcessionTracker]:
    approved_amount = offer.approved_amount
    rate = offer.interest_rate_annual
    tenure = offer.tenure_months
    fee_pct = offer.processing_fee_pct

    if lever == "amount" and increment > 0:
        approved_amount = int(round(offer.approved_amount * (1 + increment / 100)))
        tracker.amount_extended_pct = min(100.0, tracker.amount_extended_pct + increment)
    elif lever == "rate" and increment > 0:
        rate = max(0.0, offer.interest_rate_annual - increment)
        tracker.rate_discounted_pct = min(100.0, tracker.rate_discounted_pct + increment)
    elif lever == "fee" and increment > 0:
        fee_pct = max(0.0, offer.processing_fee_pct * (1 - increment / 100))
        tracker.fee_waived_pct = min(100.0, tracker.fee_waived_pct + increment)
    elif lever == "tenure" and increment > 0:
        tenure = offer.tenure_months + 24
        tracker.tenure_extended = True

    return (
        OfferTerms(
            approved_amount=approved_amount,
            tenure_months=tenure,
            interest_rate_annual=rate,
            emi_monthly=offer.emi_monthly,
            processing_fee_pct=fee_pct,
            processing_fee_amount=offer.processing_fee_amount,
            total_payable=offer.total_payable,
        ),
        tracker,
    )


def present_offer_message(
    *,
    full_name: str,
    loan_query: str,
    risk_persona: str,
    offer: OfferTerms,
) -> str:
    prompt = OFFER_PRESENTATION_PROMPT.format(
        full_name=full_name,
        loan_query=loan_query,
        risk_persona=risk_persona,
        approved_amount=offer.approved_amount,
        emi_monthly=offer.emi_monthly,
        tenure_months=offer.tenure_months,
        interest_rate_annual=offer.interest_rate_annual,
        processing_fee_amount=offer.processing_fee_amount,
    )
    return _llm_text(prompt)


def acceptance_message(offer: OfferTerms) -> str:
    prompt = ACCEPTANCE_PROMPT.format(
        approved_amount=offer.approved_amount,
        emi_monthly=offer.emi_monthly,
        tenure_months=offer.tenure_months,
    )
    return _llm_text(prompt)


def _build_offer_from_guard(guard_values: dict, fallback_offer: OfferTerms) -> OfferTerms:
    approved_amount = int(guard_values.get("approved_amount", fallback_offer.approved_amount))
    rate = float(guard_values.get("interest_rate_annual", fallback_offer.interest_rate_annual))
    tenure = int(guard_values.get("tenure_months", fallback_offer.tenure_months))
    fee_pct = float(guard_values.get("processing_fee_pct", fallback_offer.processing_fee_pct))

    r = rate / 12 / 100
    if r == 0:
        emi = approved_amount // tenure
    else:
        emi = int(approved_amount * r * (1 + r) ** tenure / ((1 + r) ** tenure - 1))
    fee_amount = int(approved_amount * fee_pct / 100)
    total_payable = emi * tenure + fee_amount

    return OfferTerms(
        approved_amount=approved_amount,
        tenure_months=tenure,
        interest_rate_annual=rate,
        emi_monthly=emi,
        processing_fee_pct=fee_pct,
        processing_fee_amount=fee_amount,
        total_payable=total_payable,
    )


def run_negotiation_turn(
    *,
    negotiation_state: NegotiationState,
    loan: LoanProduct,
    policy: PolicyInputs,
    customer_utterance: str,
    initial_offer: OfferTerms,
) -> tuple[NegotiationState, str, dict | None]:
    rounds_remaining = max(0, negotiation_state.max_rounds - negotiation_state.rounds_elapsed)
    intent_probe_prompt = NEGOTIATION_TURN_PROMPT.format(
        user_utterance=customer_utterance,
        approved_amount=negotiation_state.current_offer.approved_amount,
        emi_monthly=negotiation_state.current_offer.emi_monthly,
        tenure_months=negotiation_state.current_offer.tenure_months,
        interest_rate_annual=negotiation_state.current_offer.interest_rate_annual,
        concession_description="hold",
        rounds_remaining=rounds_remaining,
        conversion_probability=negotiation_state.conversion_probability,
    )
    probe_response = _llm_text(intent_probe_prompt)
    _, intent = _split_intent_block(probe_response)
    allowed = {
        "wants_more_amount",
        "wants_lower_emi",
        "wants_lower_rate",
        "wants_longer_tenure",
        "wants_fee_waiver",
        "accepting",
        "rejecting",
    }
    if intent not in allowed:
        intent = "rejecting"

    conversion_prob = compute_conversion_probability(negotiation_state, intent)
    recommended = recommend_concession(negotiation_state, conversion_prob, intent)
    negotiation_state.conversion_probability = conversion_prob
    negotiation_state.recommended_next_concession = recommended

    if intent == "accepting":
        negotiation_state.status = "accepted"
        acceptance_message = _llm_text(
            ACCEPTANCE_PROMPT.format(
                approved_amount=negotiation_state.current_offer.approved_amount,
                emi_monthly=negotiation_state.current_offer.emi_monthly,
                tenure_months=negotiation_state.current_offer.tenure_months,
            )
        )
        consent = capture_consent_event(
            session_id=negotiation_state.session_id,
            event_type="final_offer",
            transcript_segment=customer_utterance,
            offer_snapshot=negotiation_state.current_offer.model_dump(),
        )
        return negotiation_state, acceptance_message, consent

    if recommended == "escalate" or negotiation_state.rounds_elapsed >= negotiation_state.max_rounds:
        negotiation_state.status = "escalated"
        escalation_message = _llm_text(ESCALATION_PROMPT.format(full_name="Customer"))
        return negotiation_state, escalation_message, None

    increment = compute_concession_increment(recommended or "hold", negotiation_state, conversion_prob)
    proposed_offer, tracker = _apply_concession(
        negotiation_state.current_offer,
        recommended or "hold",
        increment,
        negotiation_state.concession_tracker,
    )

    guard = NegotiationGuard(loan, initial_offer, policy)
    guard_result = guard.propose(
        proposed_amount=proposed_offer.approved_amount,
        proposed_rate=proposed_offer.interest_rate_annual,
        proposed_tenure=proposed_offer.tenure_months,
        proposed_fee_pct=proposed_offer.processing_fee_pct,
    )

    if not guard_result.get("allowed"):
        negotiation_state.status = "escalated"
        escalation_message = _llm_text(ESCALATION_PROMPT.format(full_name="Customer"))
        return negotiation_state, escalation_message, None

    clamped = guard_result.get("clamped_values", {})
    negotiation_state.current_offer = _build_offer_from_guard(clamped, proposed_offer)
    negotiation_state.concession_tracker = tracker
    negotiation_state.rounds_elapsed += 1

    rounds_remaining = max(0, negotiation_state.max_rounds - negotiation_state.rounds_elapsed)
    concession_description = _format_concession_description(
        recommended or "hold",
        increment,
        negotiation_state.current_offer,
    )

    response_prompt = NEGOTIATION_TURN_PROMPT.format(
        user_utterance=customer_utterance,
        approved_amount=negotiation_state.current_offer.approved_amount,
        emi_monthly=negotiation_state.current_offer.emi_monthly,
        tenure_months=negotiation_state.current_offer.tenure_months,
        interest_rate_annual=negotiation_state.current_offer.interest_rate_annual,
        concession_description=concession_description,
        rounds_remaining=rounds_remaining,
        conversion_probability=conversion_prob,
    )
    response = _llm_text(response_prompt)
    spoken, _ = _split_intent_block(response)
    if not spoken:
        spoken = "I have updated the offer within policy limits."

    negotiation_state.round_log.append(
        RoundLog(
            round=negotiation_state.rounds_elapsed,
            user_utterance=customer_utterance,
            user_intent=intent,
            concession_offered=recommended,
            offer_snapshot=negotiation_state.current_offer,
        )
    )

    return negotiation_state, spoken, None
