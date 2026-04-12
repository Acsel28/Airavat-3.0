from __future__ import annotations

from fastapi import APIRouter, HTTPException

from loans8.api.schemas import NegotiationTurnRequest, NegotiationTurnResponse
from loans8.api.services.negotiation import run_negotiation_turn
from loans8.engine.audit import emit_audit_event

router = APIRouter()


@router.post("/negotiate/turn", response_model=NegotiationTurnResponse)
def negotiate_turn(payload: NegotiationTurnRequest) -> NegotiationTurnResponse:
    customer_utterance = payload.customer_utterance.strip()
    if not customer_utterance:
        raise HTTPException(status_code=400, detail="customer_utterance is required")

    negotiation_state, verbal_response, consent = run_negotiation_turn(
        negotiation_state=payload.negotiation_state,
        loan=payload.loan,
        policy=payload.policy_inputs,
        customer_utterance=customer_utterance,
        initial_offer=payload.negotiation_state.current_offer,
    )

    emit_audit_event(
        session_id=payload.session_id,
        event_type=f"NEGOTIATION_ROUND_{negotiation_state.rounds_elapsed}",
        loan_id=payload.loan.loan_id,
        terms_snapshot=negotiation_state.current_offer.model_dump(),
        customer_utterance=customer_utterance,
        agent_action=negotiation_state.recommended_next_concession or "hold",
        round_number=negotiation_state.rounds_elapsed,
        metadata={"status": negotiation_state.status},
    )

    return NegotiationTurnResponse(
        session_id=payload.session_id,
        negotiation_state=negotiation_state,
        verbal_response=verbal_response,
        status=negotiation_state.status,
        consent_record=consent,
    )
