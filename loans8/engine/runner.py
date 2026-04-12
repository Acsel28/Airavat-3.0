from __future__ import annotations

from loans8.agent.negotiation_agent import run_negotiation_turn as agent_run_negotiation_turn
from loans8.agent.retrieval import get_loan_recommendations
from loans8.api.schemas import LoanProduct, NegotiationState, OfferRequest, OfferTerms, PolicyInputs
from loans8.api.services.loan_lookup import get_loan_by_id
from loans8.api.services.session_store import load_policy_inputs, load_ranked_loans, save_policy_inputs, save_ranked_loans
from loans8.engine.consent import capture_consent_event
from loans8.engine.eligibility import run_pre_eligibility_gate
from loans8.engine.filter import hard_filter_loans
from loans8.engine.offer_engine import generate_offer
from loans8.engine.ranker import rerank_loans


def _coerce_offer_request(offer_request: dict | OfferRequest) -> OfferRequest:
    if isinstance(offer_request, OfferRequest):
        return offer_request
    return OfferRequest.model_validate(offer_request)


def search_loans(offer_request: dict) -> dict:
    payload = _coerce_offer_request(offer_request)
    query = payload.query.strip()
    if not query:
        raise ValueError("query is required")

    pre_eligibility = run_pre_eligibility_gate(payload.policy_inputs)
    save_policy_inputs(payload.session_id, payload.policy_inputs.model_dump())
    if not pre_eligibility.passed:
        return {"pre_eligibility": pre_eligibility.model_dump(), "top_3": []}

    reco = get_loan_recommendations(query, top_k=6)
    results = reco.get("results", [])
    if not results:
        return {"pre_eligibility": pre_eligibility.model_dump(), "top_3": []}

    loan_products: list[LoanProduct] = []
    for loan in results:
        try:
            loan_products.append(LoanProduct.model_validate(loan))
        except Exception:
            continue

    filtered = hard_filter_loans(loan_products, payload.policy_inputs, pre_eligibility)
    ranked = rerank_loans(filtered, payload.policy_inputs) if filtered else []

    ranked_loans = [loan.model_dump() for loan in ranked]
    save_ranked_loans(payload.session_id, ranked_loans)

    return {"pre_eligibility": pre_eligibility.model_dump(), "top_3": ranked_loans}


def generate_loan_offer(offer_request: dict, loan_choice_index: int) -> dict:
    payload = _coerce_offer_request(offer_request)

    pre_eligibility = run_pre_eligibility_gate(payload.policy_inputs)
    if not pre_eligibility.passed:
        raise ValueError(pre_eligibility.rejection_reason or "not eligible")

    ranked = load_ranked_loans(payload.session_id) or []
    if not ranked:
        raise ValueError("no ranked loans available")

    choice = loan_choice_index or 1
    if choice < 1 or choice > len(ranked):
        choice = 1

    selected = LoanProduct.model_validate(ranked[choice - 1])

    offer = generate_offer(
        loan=selected,
        policy=payload.policy_inputs,
        pre_eligibility=pre_eligibility,
        session_id=payload.session_id,
    )

    return offer.model_dump()


def run_negotiation_turn(negotiation_state: dict, user_utterance: str) -> dict:
    raw_state = dict(negotiation_state)
    loan_payload = raw_state.pop("loan", None)
    policy_payload = raw_state.pop("policy_inputs", None)
    initial_offer_payload = raw_state.pop("initial_offer", None)

    state = NegotiationState.model_validate(raw_state)

    if loan_payload:
        loan = LoanProduct.model_validate(loan_payload)
    else:
        loan = get_loan_by_id(state.loan_id)
        if not loan:
            raise ValueError("loan_id not found")

    if policy_payload:
        policy = PolicyInputs.model_validate(policy_payload)
    else:
        policy_inputs = load_policy_inputs(state.session_id)
        if not policy_inputs:
            raise ValueError("policy_inputs not found for session")
        policy = PolicyInputs.model_validate(policy_inputs)

    if initial_offer_payload:
        initial_offer = OfferTerms.model_validate(initial_offer_payload)
    else:
        initial_offer = OfferTerms.model_validate(state.current_offer.model_dump())

    updated_state, agent_message, _ = agent_run_negotiation_turn(
        negotiation_state=state,
        loan=loan,
        policy=policy,
        customer_utterance=user_utterance,
        initial_offer=initial_offer,
    )

    return {
        "agent_message": agent_message,
        "updated_state": updated_state.model_dump(),
        "status": updated_state.status,
    }


def accept_offer(negotiation_state: dict, user_utterance: str) -> dict:
    raw_state = dict(negotiation_state)
    raw_state.pop("loan", None)
    raw_state.pop("policy_inputs", None)
    raw_state.pop("initial_offer", None)
    state = NegotiationState.model_validate(raw_state)
    consent = capture_consent_event(
        session_id=state.session_id,
        event_type="final_offer",
        transcript_segment=user_utterance,
        offer_snapshot=state.current_offer.model_dump(),
    )
    return consent
