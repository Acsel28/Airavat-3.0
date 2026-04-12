from __future__ import annotations

import json
from datetime import datetime, timezone

from workflow1.agent.collection_agent import agent_graph, build_phase1_output
from workflow1.schema import AgentState, FieldConfidence

TEST_KYC = {
    "kyc_full_name": "Rahul Mehta",
    "kyc_dob": "1990-05-15",
    "kyc_age": 34,
    "kyc_gender": "male",
    "kyc_pan": "ABCPM1234D",
    "kyc_city": "Mumbai",
    "kyc_state": "Maharashtra",
    "kyc_verified": True,
}

TEST_INCOME = {
    "emp_employer_name": "Infosys Ltd",
    "emp_employment_type": "salaried",
    "emp_gross_monthly_income": 95000,
    "emp_net_monthly_income": 78000,
    "emp_pf_deducted": True,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _last_assistant_message(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            return str(msg.get("content", ""))
    return ""


def build_test_state(session_id: str) -> AgentState:
    return AgentState(
        session_id=session_id,
        full_name=TEST_KYC["kyc_full_name"],
        dob=TEST_KYC["kyc_dob"],
        age=TEST_KYC["kyc_age"],
        gender=TEST_KYC["kyc_gender"],
        pan=TEST_KYC["kyc_pan"],
        city=TEST_KYC["kyc_city"],
        state=TEST_KYC["kyc_state"],
        kyc_verified=TEST_KYC["kyc_verified"],
        employer_name=TEST_INCOME["emp_employer_name"],
        employment_type=TEST_INCOME["emp_employment_type"],
        gross_monthly_income=TEST_INCOME["emp_gross_monthly_income"],
        net_monthly_income=TEST_INCOME["emp_net_monthly_income"],
        pf_deducted=TEST_INCOME["emp_pf_deducted"],
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
        phase1_complete=False,
        stage="warmup",
        warmup_turns_done=0,
        retry_counts={},
    )


def main() -> None:
    session_id = "test-session-001"
    state = build_test_state(session_id)

    config = {"configurable": {"thread_id": session_id}}
    state = agent_graph.invoke(state, config=config)
    opening = _last_assistant_message(state["messages"])
    if opening:
        print(f"Agent: {opening}\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            print("(empty — please type a response)\n")
            continue

        state["messages"].append(
            {"role": "user", "content": user_input, "timestamp": _now_iso(), "stage": state.get("stage")}
        )
        state["turn_count"] += 1
        state = agent_graph.invoke(state, config=config)

        assistant_reply = _last_assistant_message(state["messages"])
        if assistant_reply:
            print(f"\nAgent: {assistant_reply}\n")

        if state.get("phase1_complete"):
            break

    output = build_phase1_output(state)
    print("\n--- Phase 1 Output ---")
    print(json.dumps(output.model_dump(), indent=2))
    print("\nField confidence:")
    print(json.dumps(state.get("field_confidence", {}), indent=2))
    print("\nLow confidence flags:")
    print(state.get("low_confidence_flags", []))
    print("\nComputed metrics:")
    print(f"credit_score: {state.get('credit_score')}")
    print(f"foir_current: {state.get('foir_current')}")
    print(f"max_eligible_emi: {state.get('max_eligible_emi')}")


if __name__ == "__main__":
    main()
