from __future__ import annotations

import json
import os

from langchain_google_genai import ChatGoogleGenerativeAI

from loans8.agent.prompts import (
    NEGOTIATION_ACCEPTED_MESSAGE,
    NEGOTIATION_ESCALATION_MESSAGE,
    NEGOTIATION_INTENT_CLASSIFIER_PROMPT,
)
from loans8.agent.retrieval import get_loan_recommendations
from loans8.api.schemas import ConcessionTracker, LoanProduct, NegotiationState, OfferTerms, PolicyInputs
from loans8.engine.consent import capture_consent_event
from loans8.engine.conversion import compute_concession_increment, compute_conversion_probability, recommend_concession
from loans8.engine.eligibility import run_pre_eligibility_gate
from loans8.engine.filter import hard_filter_loans
from loans8.engine.negotiation_guard import NegotiationGuard
from loans8.engine.offer_engine import generate_offer
from loans8.engine.ranker import rerank_loans
from loans8.engine.rate_limit import RequestRateLimiter

TEST_REQUEST = {
    "session_id": "test-session-001",
    "query": "I want to buy a house for my family in Mumbai",
    "loan_choice_index": None,
    "policy_inputs": {
        "age": 34,
        "employment_type": "salaried",
        "gross_monthly_income": 95000,
        "net_monthly_income": 78000,
        "existing_emi_monthly": 8000,
        "credit_score": 720,
        "fraud_score": 10,
        "risk_persona": "standard",
        "intent_category": "home_purchase",
        "requested_amount": 4500000,
        "preferred_tenure_months": 240,
        "collateral_offered": True,
        "collateral_value": 5500000,
        "missed_payments_last_12m": 0,
    },
    "negotiate": False,
}

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


def _apply_concession(offer: OfferTerms, lever: str, increment: float, tracker: ConcessionTracker) -> OfferTerms:
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

    return OfferTerms(
        approved_amount=approved_amount,
        tenure_months=tenure,
        interest_rate_annual=rate,
        emi_monthly=offer.emi_monthly,
        processing_fee_pct=fee_pct,
        processing_fee_amount=offer.processing_fee_amount,
        total_payable=offer.total_payable,
    )


def _score_for_rerank(loan: LoanProduct, policy: PolicyInputs) -> float:
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


def _explain_filter_rejections(loan: LoanProduct, policy: PolicyInputs) -> list[str]:
    reasons: list[str] = []
    e = loan.eligibility
    t = loan.product_terms

    if policy.credit_score < e.min_credit_score:
        reasons.append("credit_score_below_min")
    if e.max_credit_score and policy.credit_score > e.max_credit_score:
        reasons.append("credit_score_above_max")
    if policy.net_monthly_income < e.min_net_income:
        reasons.append("net_income_below_min")
    if policy.employment_type not in e.allowed_employment_types:
        reasons.append("employment_type_not_allowed")
    max_tenure_for_age = (65 - policy.age) * 12
    if t.min_tenure_months > max_tenure_for_age:
        reasons.append("age_tenure_mismatch")
    if policy.requested_amount < t.min_amount:
        reasons.append("requested_amount_below_min")
    if e.collateral_required and not policy.collateral_offered:
        reasons.append("collateral_required")

    return reasons


def main() -> None:
    policy = PolicyInputs(**TEST_REQUEST["policy_inputs"])
    pre_elig = run_pre_eligibility_gate(policy)
    print("Pre-eligibility result:")
    print(pre_elig.model_dump())

    reco = get_loan_recommendations(TEST_REQUEST["query"], top_k=6)
    print("\nTop 6 raw results:")
    for loan in reco["results"]:
        print(f"- {loan['loan_name']}")

    loan_products: list[LoanProduct] = []
    for loan in reco["results"]:
        try:
            loan_products.append(LoanProduct.model_validate(loan))
        except Exception:
            continue

    filtered = hard_filter_loans(loan_products, policy, pre_elig)
    print("\nFilter results:")
    for loan in loan_products:
        if loan in filtered:
            print(f"PASS: {loan.loan_name}")
        else:
            reasons = _explain_filter_rejections(loan, policy)
            print(f"FAIL: {loan.loan_name} -> {', '.join(reasons) or 'unknown'}")

    ranked = rerank_loans(filtered, policy)
    print("\nTop 3 reranked:")
    for idx, loan in enumerate(ranked, 1):
        print(f"{idx}. {loan.loan_name} (score={_score_for_rerank(loan, policy):.3f})")

    while True:
        choice = input("Pick a loan (1/2/3): ").strip()
        try:
            selected_loan = ranked[int(choice) - 1]
            break
        except (IndexError, ValueError):
            print("Please enter 1, 2, or 3.")

    offer = generate_offer(
        loan=selected_loan,
        policy=policy,
        pre_eligibility=pre_elig,
        session_id=TEST_REQUEST["session_id"],
    )
    print("\nGenerated offer:")
    print(json.dumps(offer.model_dump(), indent=2))

    negotiate = input("Do you want to negotiate? (y/n): ").strip().lower()
    if negotiate not in {"y", "yes"}:
        return

    negotiation_state = NegotiationState(
        session_id=TEST_REQUEST["session_id"],
        loan_id=selected_loan.loan_id,
        rounds_elapsed=0,
        max_rounds=8,
        status="active",
        hard_limits=selected_loan.negotiation_limits.model_dump(),
        current_offer=offer.offer,
        concession_tracker=ConcessionTracker(),
        conversion_probability=0.5,
        recommended_next_concession=None,
        round_log=[],
    )

    guard = NegotiationGuard(selected_loan, offer.offer, policy)

    while negotiation_state.status == "active":
        print("\nCurrent offer:")
        print(negotiation_state.current_offer.model_dump())
        utterance = input("Your response (or 'quit'): ").strip()
        if utterance.lower() == "quit":
            negotiation_state.status = "abandoned"
            break

        parsed = _llm_json(NEGOTIATION_INTENT_CLASSIFIER_PROMPT.format(customer_utterance=utterance))
        intent = parsed.get("user_intent", "rejecting")
        print(f"Classified intent: {intent}")

        conversion_prob = compute_conversion_probability(negotiation_state, intent)
        recommended = recommend_concession(negotiation_state, conversion_prob, intent)
        print(f"Conversion probability: {conversion_prob:.2f}")
        print(f"Recommended lever: {recommended}")

        if intent == "accepting":
            negotiation_state.status = "accepted"
            consent = capture_consent_event(
                session_id=negotiation_state.session_id,
                event_type="final_offer",
                transcript_segment=utterance,
                offer_snapshot=negotiation_state.current_offer.model_dump(),
            )
            print(NEGOTIATION_ACCEPTED_MESSAGE)
            print("Consent record:")
            print(json.dumps(consent, indent=2))
            break

        if recommended == "escalate" or negotiation_state.rounds_elapsed >= negotiation_state.max_rounds:
            negotiation_state.status = "escalated"
            print(NEGOTIATION_ESCALATION_MESSAGE)
            break

        increment = compute_concession_increment(recommended or "hold", negotiation_state, conversion_prob)
        proposed = _apply_concession(
            negotiation_state.current_offer,
            recommended or "hold",
            increment,
            negotiation_state.concession_tracker,
        )
        guard_result = guard.propose(
            proposed_amount=proposed.approved_amount,
            proposed_rate=proposed.interest_rate_annual,
            proposed_tenure=proposed.tenure_months,
            proposed_fee_pct=proposed.processing_fee_pct,
        )
        print(f"Guard result: {guard_result}")
        if not guard_result.get("allowed"):
            negotiation_state.status = "escalated"
            print(NEGOTIATION_ESCALATION_MESSAGE)
            break

        clamped = guard_result.get("clamped_values", {})
        approved_amount = int(clamped.get("approved_amount", proposed.approved_amount))
        rate = float(clamped.get("interest_rate_annual", proposed.interest_rate_annual))
        tenure = int(clamped.get("tenure_months", proposed.tenure_months))
        fee_pct = float(clamped.get("processing_fee_pct", proposed.processing_fee_pct))

        r = rate / 12 / 100
        if r == 0:
            emi = approved_amount // tenure
        else:
            emi = int(approved_amount * r * (1 + r) ** tenure / ((1 + r) ** tenure - 1))
        fee_amount = int(approved_amount * fee_pct / 100)
        total_payable = emi * tenure + fee_amount

        negotiation_state.current_offer = OfferTerms(
            approved_amount=approved_amount,
            tenure_months=tenure,
            interest_rate_annual=rate,
            emi_monthly=emi,
            processing_fee_pct=fee_pct,
            processing_fee_amount=fee_amount,
            total_payable=total_payable,
        )
        negotiation_state.rounds_elapsed += 1
        negotiation_state.recommended_next_concession = recommended
        negotiation_state.conversion_probability = conversion_prob

        negotiation_state.round_log.append(
            {
                "round": negotiation_state.rounds_elapsed,
                "user_utterance": utterance,
                "user_intent": intent,
                "concession_offered": recommended,
                "offer_snapshot": negotiation_state.current_offer.model_dump(),
            }
        )

        print("New offer:")
        print(negotiation_state.current_offer.model_dump())

    print("\nFinal NegotiationState:")
    print(json.dumps(negotiation_state.model_dump(), indent=2))


if __name__ == "__main__":
    main()
