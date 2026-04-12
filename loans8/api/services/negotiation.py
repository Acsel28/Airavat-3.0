from __future__ import annotations

import json
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from loans8.agent.negotiation_agent import run_negotiation_turn as agent_run_negotiation_turn
from loans8.api.schemas import ConcessionTracker, NegotiationState, OfferTerms, RoundLog
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


def _llm_json(prompt: str) -> dict:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite", temperature=0)
    _get_negotiation_rate_limiter().acquire()
    response = llm.invoke(prompt)
    content = response.content if isinstance(response.content, str) else str(response.content)
    text = content.strip()
    if text.startswith("```"):
        text = "\n".join(line for line in text.splitlines() if not line.strip().startswith("```"))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except Exception:
        return {}


def _format_offer(offer: OfferTerms) -> str:
    return (
        f"amount={offer.approved_amount}, rate={offer.interest_rate_annual:.2f}, "
        f"tenure={offer.tenure_months}, emi={offer.emi_monthly}, fee={offer.processing_fee_pct:.2f}%"
    )


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
        tenure = offer.tenure_months + 12
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


def run_negotiation_turn(
    *,
    negotiation_state: NegotiationState,
    loan,
    policy,
    customer_utterance: str,
    initial_offer: OfferTerms,
) -> tuple[NegotiationState, str, dict | None]:
    return agent_run_negotiation_turn(
        negotiation_state=negotiation_state,
        loan=loan,
        policy=policy,
        customer_utterance=customer_utterance,
        initial_offer=initial_offer,
    )
