from __future__ import annotations

from fastapi import APIRouter, HTTPException

from loans8.api.schemas import PolicyInputs
from loans8.engine.runner import search_loans

router = APIRouter()


class LoanSearchRequest(PolicyInputs):
    session_id: str
    query: str


@router.post("/loans/search")
def loan_search(payload: LoanSearchRequest) -> dict:
    try:
        result = search_loans(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "top_3_loans": result.get("top_3", []),
        "pre_eligibility": result.get("pre_eligibility"),
    }
