from __future__ import annotations

from fastapi import APIRouter, HTTPException

from loans8.agent.prompts import NEGOTIATION_VERBAL_OFFER
from loans8.agent.retrieval import get_loan_recommendations
from loans8.api.schemas import GeneratedOffer, LoanProduct, OfferRequest, OfferResponse, RetrievalInfo
from loans8.engine.audit import emit_audit_event, get_session_audit_trail
from loans8.engine.eligibility import run_pre_eligibility_gate
from loans8.engine.filter import hard_filter_loans
from loans8.engine.offer_engine import generate_offer
from loans8.engine.ranker import rerank_loans

router = APIRouter()


def _fmt_inr(value: int) -> str:
    return f"₹{int(value):,}"


@router.post("/offer", response_model=OfferResponse)
def create_offer(payload: OfferRequest) -> OfferResponse:
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    pre_eligibility = run_pre_eligibility_gate(payload.policy_inputs)
    if not pre_eligibility.passed:
        rejection = GeneratedOffer(
            session_id=payload.session_id,
            loan_id="",
            loan_name="pre_eligibility",
            generated_at="",
            offer={
                "approved_amount": 0,
                "tenure_months": 0,
                "interest_rate_annual": 0.0,
                "emi_monthly": 0,
                "processing_fee_pct": 0.0,
                "processing_fee_amount": 0,
                "total_payable": 0,
            },
            eligibility_summary={
                "foir_after_loan": pre_eligibility.foir_current,
                "foir_gate_passed": False,
                "credit_score_gate_passed": True,
                "age_tenure_gate_passed": True,
                "fraud_gate_passed": False,
                "final_decision": "rejected",
                "rejection_reason": pre_eligibility.rejection_reason,
            },
        )
        emit_audit_event(
            session_id=payload.session_id,
            event_type="PRE_ELIGIBILITY_REJECTED",
            loan_id="",
            terms_snapshot=rejection.model_dump(),
            customer_utterance=query,
            agent_action="pre_eligibility",
            metadata={"reason": pre_eligibility.rejection_reason},
        )
        return OfferResponse(
            session_id=payload.session_id,
            retrieval=RetrievalInfo(method="pre_eligibility", intent=None, results=[]),
            selected_loan=None,
            offer=rejection,
            tts_script=pre_eligibility.rejection_reason,
            audit_trail=get_session_audit_trail(payload.session_id),
        )

    reco = get_loan_recommendations(query, top_k=6)
    results = reco.get("results", [])
    retrieval = RetrievalInfo(
        method=reco.get("retrieval_method", "unknown"),
        intent=reco.get("intent"),
        results=results,
    )

    if not results:
        return OfferResponse(
            session_id=payload.session_id,
            retrieval=retrieval,
            selected_loan=None,
            offer=None,
            tts_script=None,
            audit_trail=[],
        )

    loan_products: list[LoanProduct] = []
    for loan in results:
        try:
            loan_products.append(LoanProduct.model_validate(loan))
        except Exception:
            continue

    filtered = hard_filter_loans(loan_products, payload.policy_inputs, pre_eligibility)
    if not filtered:
        message = "No eligible loan products found for your profile. A specialist will contact you."
        return OfferResponse(
            session_id=payload.session_id,
            retrieval=retrieval,
            selected_loan=None,
            offer=None,
            tts_script=message,
            audit_trail=get_session_audit_trail(payload.session_id),
        )

    ranked = rerank_loans(filtered, payload.policy_inputs)
    choice = payload.loan_choice_index or 1
    if choice < 1 or choice > len(ranked):
        choice = 1
    selected_loan = ranked[choice - 1]

    offer = generate_offer(
        loan=selected_loan,
        policy=payload.policy_inputs,
        pre_eligibility=pre_eligibility,
        session_id=payload.session_id,
    )
    tts_script = NEGOTIATION_VERBAL_OFFER.format(
        amount=_fmt_inr(offer.offer.approved_amount),
        rate=offer.offer.interest_rate_annual,
        tenure=offer.offer.tenure_months,
        emi=_fmt_inr(offer.offer.emi_monthly),
    )

    emit_audit_event(
        session_id=payload.session_id,
        event_type="OFFER_GENERATED",
        loan_id=offer.loan_id,
        terms_snapshot=offer.model_dump(),
        customer_utterance=query,
        agent_action="offer_generation",
    )

    audit_trail = get_session_audit_trail(payload.session_id)

    return OfferResponse(
        session_id=payload.session_id,
        retrieval=retrieval,
        selected_loan=selected_loan.model_dump(),
        offer=offer,
        tts_script=tts_script,
        audit_trail=audit_trail,
    )
