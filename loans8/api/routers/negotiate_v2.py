from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from loans8.agent.prompts import NEGOTIATION_START_MESSAGE
from loans8.api.schemas import NegotiationState, OfferTerms, PolicyInputs
from loans8.api.services.loan_lookup import get_loan_by_id
from loans8.api.services.negotiation import run_negotiation_turn
from loans8.api.services.negotiation_store import load_negotiation_state, save_negotiation_state
from loans8.api.services.session_store import load_policy_inputs
from loans8.engine.audit import emit_audit_event

router = APIRouter()


class NegotiateStartRequest(BaseModel):
    session_id: str
    loan_id: str
    offer: OfferTerms


@router.post("/negotiate/start")
def negotiate_start(payload: NegotiateStartRequest) -> dict:
    policy_inputs = load_policy_inputs(payload.session_id)
    if not policy_inputs:
        raise HTTPException(status_code=400, detail="policy_inputs not found for session")

    loan = get_loan_by_id(payload.loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="loan_id not found")

    negotiation_id = str(uuid.uuid4())
    state = NegotiationState(
        session_id=payload.session_id,
        loan_id=loan.loan_id,
        rounds_elapsed=0,
        max_rounds=8,
        status="active",
        hard_limits=loan.negotiation_limits.model_dump(),
        current_offer=payload.offer,
    )
    emit_audit_event(
        session_id=payload.session_id,
        event_type="NEGOTIATION_STARTED",
        loan_id=loan.loan_id,
        terms_snapshot=payload.offer.model_dump(),
        customer_utterance="",
        agent_action="negotiate_start",
        round_number=0,
    )
    save_negotiation_state(
        negotiation_id=negotiation_id,
        session_id=payload.session_id,
        loan_id=loan.loan_id,
        negotiation_state=state.model_dump(),
        initial_offer=payload.offer.model_dump(),
    )
    return {
        "negotiation_id": negotiation_id,
        "agent_message": NEGOTIATION_START_MESSAGE,
        "current_offer": state.current_offer.model_dump(),
    }


class NegotiateTurnRequest(BaseModel):
    user_message: str


@router.post("/negotiate/{negotiation_id}/turn")
def negotiate_turn(negotiation_id: str, payload: NegotiateTurnRequest) -> dict:
    user_message = payload.user_message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="user_message is required")

    stored = load_negotiation_state(negotiation_id)
    if not stored:
        raise HTTPException(status_code=404, detail="negotiation_id not found")

    policy_inputs = load_policy_inputs(stored["session_id"])
    if not policy_inputs:
        raise HTTPException(status_code=400, detail="policy_inputs not found for session")

    loan = get_loan_by_id(stored["loan_id"])
    if not loan:
        raise HTTPException(status_code=404, detail="loan_id not found")

    negotiation_state = NegotiationState.model_validate(stored["negotiation_state"])
    initial_offer = OfferTerms.model_validate(stored["initial_offer"])
    policy = PolicyInputs.model_validate(policy_inputs)

    negotiation_state, verbal_response, consent = run_negotiation_turn(
        negotiation_state=negotiation_state,
        loan=loan,
        policy=policy,
        customer_utterance=user_message,
        initial_offer=initial_offer,
    )

    emit_audit_event(
        session_id=stored["session_id"],
        event_type=f"NEGOTIATION_ROUND_{negotiation_state.rounds_elapsed}",
        loan_id=loan.loan_id,
        terms_snapshot=negotiation_state.current_offer.model_dump(),
        customer_utterance=user_message,
        agent_action=negotiation_state.recommended_next_concession or "hold",
        round_number=negotiation_state.rounds_elapsed,
        metadata={"status": negotiation_state.status},
    )

    save_negotiation_state(
        negotiation_id=negotiation_id,
        session_id=stored["session_id"],
        loan_id=loan.loan_id,
        negotiation_state=negotiation_state.model_dump(),
        initial_offer=initial_offer.model_dump(),
    )

    return {
        "agent_message": verbal_response,
        "current_offer": negotiation_state.current_offer.model_dump(),
        "conversion_probability": negotiation_state.conversion_probability,
        "concession_offered": negotiation_state.recommended_next_concession,
        "status": negotiation_state.status,
        "rounds_elapsed": negotiation_state.rounds_elapsed,
    }


class NegotiateAcceptRequest(BaseModel):
    user_utterance: str


@router.post("/negotiate/{negotiation_id}/accept")
def negotiate_accept(negotiation_id: str, payload: NegotiateAcceptRequest) -> dict:
    if not payload.user_utterance.strip():
        raise HTTPException(status_code=400, detail="user_utterance is required")

    stored = load_negotiation_state(negotiation_id)
    if not stored:
        raise HTTPException(status_code=404, detail="negotiation_id not found")

    negotiation_state = NegotiationState.model_validate(stored["negotiation_state"])

    from loans8.engine.consent import capture_consent_event

    consent = capture_consent_event(
        session_id=stored["session_id"],
        event_type="final_offer",
        transcript_segment=payload.user_utterance,
        offer_snapshot=negotiation_state.current_offer.model_dump(),
    )
    return {"consent_record": consent, "final_offer": negotiation_state.current_offer.model_dump()}
