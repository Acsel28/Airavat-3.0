from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from config import OPTIONAL_COLLECTED_FIELDS, REQUIRED_COLLECTED_FIELDS
from dependencies import log_handoff, log_turn, setup_db
from schema import AgentState, FieldConfidence
from session_store import init_sessions_table, load_state, save_state
from stt import router as stt_router

langsmith_setup.bootstrap()


class SessionStartRequest(BaseModel):
    full_name: str
    dob: str
    age: int
    gender: str
    pan: str
    city: str
    state: str
    kyc_verified: bool
    employer_name: str
    employment_type: str
    gross_monthly_income: int
    net_monthly_income: int
    pf_deducted: bool


class SessionStartResponse(BaseModel):
    session_id: str
    agent_message: str


class SessionTurnRequest(BaseModel):
    user_message: str


class SessionTurnResponse(BaseModel):
    agent_message: str
    collected_fields: dict
    field_confidence: dict
    low_confidence_flags: list
    pending_fields: list
    stage: str
    phase1_complete: bool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_initial_state(session_id: str, payload: SessionStartRequest) -> AgentState:
    return AgentState(
        session_id=session_id,
        full_name=payload.full_name,
        dob=payload.dob,
        age=payload.age,
        gender=payload.gender,
        pan=payload.pan,
        city=payload.city,
        state=payload.state,
        kyc_verified=payload.kyc_verified,
        employer_name=payload.employer_name,
        employment_type=payload.employment_type,
        gross_monthly_income=payload.gross_monthly_income,
        net_monthly_income=payload.net_monthly_income,
        pf_deducted=payload.pf_deducted,
        existing_emi_monthly=None,
        active_loan_count=None,
        missed_payments_last_12m=None,
        collateral_offered=None,
        collateral_type=None,
        collateral_value=None,
        primary_bank=None,
        loan_query_free_text=None,
        requested_amount=None,
        preferred_tenure_months=None,
        urgency=None,
        intent_category=None,
        intent_confidence=None,
        risk_persona=None,
        transcript_contradiction_flag=False,
        credit_score=None,
        fraud_score=None,
        foir_current=None,
        max_eligible_emi=None,
        max_eligible_amount_approx=None,
        field_confidence=FieldConfidence().model_dump(),
        low_confidence_flags=[],
        pending_clarifications=[],
        liveness_passed=False,
        age_kyc_delta=0,
        consent_data_collection=None,
        consent_bureau_pull=None,
        phase1_completed_at=None,
        messages=[],
        turn_count=0,
        turn_number=0,
        phase1_complete=False,
        stage="warmup",
        warmup_turns_done=0,
        retry_counts={},
    )


def _last_assistant_message(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return str(msg.get("content", ""))
    return ""


def _snapshot_fields(state: AgentState) -> dict:
    keys = [
        "existing_emi_monthly",
        "active_loan_count",
        "missed_payments_last_12m",
        "collateral_offered",
        "collateral_type",
        "collateral_value",
        "primary_bank",
        "loan_query_free_text",
        "requested_amount",
        "preferred_tenure_months",
        "urgency",
        "intent_category",
        "intent_confidence",
        "risk_persona",
        "transcript_contradiction_flag",
        "credit_score",
        "fraud_score",
        "foir_current",
        "max_eligible_emi",
        "max_eligible_amount_approx",
    ]
    return {k: state.get(k) for k in keys}


def _pending_fields(state: AgentState) -> list[str]:
    pending = [f for f in REQUIRED_COLLECTED_FIELDS if state.get(f) is None]
    if state.get("collateral_offered") is True:
        for field in ["collateral_type", "collateral_value"]:
            if state.get(field) is None:
                pending.append(field)
    for field in OPTIONAL_COLLECTED_FIELDS:
        if state.get(field) is None:
            pending.append(field)
    return list(dict.fromkeys(pending))


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_db()
    init_sessions_table()
    from stt import transcriber

    _ = transcriber.model
    from stt import storage as stt_storage

    stt_storage.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(stt_router.router, prefix="")


@app.post("/session/start", response_model=SessionStartResponse)
def session_start(payload: SessionStartRequest) -> SessionStartResponse:
    session_id = str(uuid.uuid4())
    state = _build_initial_state(session_id, payload)

    config = {"configurable": {"thread_id": session_id}}
    state = agent_graph.invoke(state, config=config)

    response = _last_assistant_message(state["messages"])
    save_state(session_id, state)

    return SessionStartResponse(session_id=session_id, agent_message=response)


@app.post("/session/{session_id}/turn", response_model=SessionTurnResponse)
def session_turn(session_id: str, payload: SessionTurnRequest) -> SessionTurnResponse:
    state = load_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="session_id not found")

    user_message = payload.user_message.strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="user_message is required")

    state["messages"].append(
        {"role": "user", "content": user_message, "timestamp": _now_iso(), "stage": state.get("stage")}
    )
    state["turn_count"] += 1

    config = {"configurable": {"thread_id": session_id}}
    state = agent_graph.invoke(state, config=config)

    response = _last_assistant_message(state["messages"])

    log_turn(
        session_id=session_id,
        phase="collecting",
        fields_snap=_snapshot_fields(state),
        agent_said=response,
        user_said=user_message,
    )

    if state.get("phase1_complete"):
        try:
            handoff = build_phase1_output(state).model_dump()
            log_handoff(session_id, handoff)
        except Exception:
            pass

    save_state(session_id, state)

    collected_fields = {f: state.get(f) for f in REQUIRED_COLLECTED_FIELDS + OPTIONAL_COLLECTED_FIELDS}

    return SessionTurnResponse(
        agent_message=response,
        collected_fields=collected_fields,
        field_confidence=state.get("field_confidence", {}),
        low_confidence_flags=state.get("low_confidence_flags", []),
        pending_fields=_pending_fields(state),
        stage=state.get("stage", ""),
        phase1_complete=bool(state.get("phase1_complete")),
    )


@app.get("/session/{session_id}/state")
def session_state(session_id: str) -> dict:
    state = load_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="session_id not found")
    return state
