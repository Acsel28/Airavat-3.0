from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from loans8.api.schemas import GeneratedOffer, PolicyInputs
from loans8.engine.runner import generate_loan_offer

router = APIRouter()


class OfferCreateRequest(BaseModel):
    session_id: str
    loan_choice_index: int
    policy_inputs: PolicyInputs


@router.post("/loans/offer")
def create_offer(payload: OfferCreateRequest) -> GeneratedOffer:
    try:
        result = generate_loan_offer(payload.model_dump(), payload.loan_choice_index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return GeneratedOffer.model_validate(result)
