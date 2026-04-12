from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from workflow1 import langsmith_setup
from workflow1.agent.collection_agent import agent_graph, build_phase1_output
from workflow1.agent.prompts import (
    MAIN_AGENT_PREFIX,
    MAIN_BANNER_SUBTITLE,
    MAIN_BANNER_TITLE,
    MAIN_BANNER_TOP,
    MAIN_CANCELLED_MESSAGE,
    MAIN_EMPTY_INPUT_WARNING,
    MAIN_EXIT_KEYWORDS,
    MAIN_HANDOFF_HEADER_1,
    MAIN_HANDOFF_SUCCESS,
    MAIN_SESSION_ID_TEMPLATE,
    MAIN_USER_PROMPT,
    MAIN_VALIDATION_WARN_TEMPLATE,
)
from workflow1.dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from workflow1.schema import AgentState, FieldConfidence

langsmith_setup.bootstrap()


def build_initial_state(session_id: str) -> AgentState:
    return AgentState(
        session_id=session_id,
        full_name="Unknown",
        dob="1990-01-01",
        age=34,
        gender="unknown",
        pan="UNKNOWN",
        city="",
        state="",
        kyc_verified=True,
        employer_name="",
        employment_type="salaried",
        gross_monthly_income=95000,
        net_monthly_income=78000,
        pf_deducted=True,
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def run_phase1() -> dict:
    print(MAIN_BANNER_TOP)
    print(MAIN_BANNER_TITLE)
    print(MAIN_BANNER_SUBTITLE)
    print(MAIN_BANNER_TOP + "\n")

    setup_db()
    session_id: str = str(uuid.uuid4())
    print(MAIN_SESSION_ID_TEMPLATE.format(session_id=session_id))

    state = build_initial_state(session_id)
    state["stage"] = "warmup"
    state["warmup_turns_done"] = 0
    state["retry_counts"] = {}

    config = {"configurable": {"thread_id": session_id}}
    state = agent_graph.invoke(state, config=config)
    response = _last_assistant_message(state["messages"])
    if response:
        print(MAIN_AGENT_PREFIX.format(text=response) + "\n")

    handoff_payload: dict = {}

    while True:
        user_input: str = input(MAIN_USER_PROMPT).strip()

        if not user_input:
            print(MAIN_EMPTY_INPUT_WARNING)
            continue
        if user_input.lower() in MAIN_EXIT_KEYWORDS:
            print(MAIN_CANCELLED_MESSAGE)
            break

        state["messages"].append(
            {"role": "user", "content": user_input, "timestamp": _now_iso(), "stage": state.get("stage")}
        )
        state["turn_count"] += 1
        state = agent_graph.invoke(state, config=config)

        response = _last_assistant_message(state["messages"])
        if response:
            print("\n" + MAIN_AGENT_PREFIX.format(text=response) + "\n")

        log_turn(
            session_id=session_id,
            phase="collecting",
            fields_snap=_snapshot_fields(state),
            agent_said=response,
            user_said=user_input,
        )

        if state.get("phase1_complete"):
            try:
                handoff = build_phase1_output(state).model_dump()
                log_handoff(session_id, handoff)
                print(MAIN_BANNER_TOP)
                print(MAIN_HANDOFF_HEADER_1)
                print(MAIN_BANNER_TOP)
                print(json.dumps(handoff, indent=2))
                print(MAIN_HANDOFF_SUCCESS)
                handoff_payload = handoff
            except Exception as exc:
                print(MAIN_VALIDATION_WARN_TEMPLATE.format(error=exc))
            break

    print_audit_trail(session_id)
    return handoff_payload


def main() -> None:
    _ = run_phase1()


if __name__ == "__main__":
    main()
