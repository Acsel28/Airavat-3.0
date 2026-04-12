from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
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
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
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
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
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
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
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
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
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
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
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
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
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
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import langsmith_setup
from agent.collection_agent import agent_graph, build_phase1_output
from agent.prompts import (
    MAIN_AGENT_PREFIX,
    MAIN_BANNER_SUBTITLE,
    MAIN_BANNER_TITLE,
    MAIN_BANNER_TOP,
    MAIN_CANCELLED_MESSAGE,
    MAIN_EMPTY_INPUT_WARNING,
    MAIN_EXIT_KEYWORDS,
    MAIN_SESSION_ID_TEMPLATE,
    MAIN_USER_PROMPT,
    MAIN_VALIDATION_WARN_TEMPLATE,
)
from dependencies import log_handoff, log_turn, print_audit_trail, setup_db
from schema import AgentState, FieldConfidence

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
        preferred_tenure_months=None,
        urgency=None,)
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
def run_phase1() -> dict:
    pass

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


def _prompt_yes_no(prompt: str) -> bool:
    while True:
        raw = input(prompt).strip().lower()
        if raw in {"yes", "y"}:
            return True
        if raw in {"no", "n"}:
            return False
        print("  (please answer yes or no)")


def _print_handoff_review(handoff: dict, low_confidence: list[str]) -> None:
    print(MAIN_BANNER_TOP)
    print(MAIN_APPROVAL_HEADER)
    print(MAIN_BANNER_TOP)
    print(json.dumps(handoff, indent=2))
    if low_confidence:
        print("\n  Low confidence fields:")
        print("  - " + ", ".join(low_confidence))


def _post_loans8_offer(handoff: dict, base_url: str) -> tuple[bool, dict | str]:
    payload = {
        "session_id": handoff["session_id"],
        "query": handoff["query"],
        "loan_choice_index": 1,
        "policy_inputs": handoff["policy_inputs"],
        "negotiate": False,
        "negotiation_inputs": [],
    }
    url = urllib.parse.urljoin(base_url.rstrip("/") + "/", "loan/offer")
    return handoff_payload


def main() -> None:
     _ = run_phase1()
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return True, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if hasattr(exc, "read") else ""
        message = f"{exc.code} {exc.reason} {body}".strip()
        return False, message
    except Exception as exc:
        return False, str(exc)


def main() -> None:
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
                _print_handoff_review(handoff, state.get("low_confidence_flags", []))
                approved = _prompt_yes_no(MAIN_APPROVAL_PROMPT)
                log_approval_decision(session_id, approved, handoff)
                if not approved:
                    print(MAIN_APPROVAL_REJECTED)
                    break

                print(MAIN_APPROVAL_APPROVED)
                log_handoff(session_id, handoff)

                print(MAIN_BANNER_TOP)
                print(MAIN_HANDOFF_HEADER_1)
                print(MAIN_BANNER_TOP)

                loans8_base_url = os.getenv("LOANS8_API_BASE", "http://localhost:8000")
                ok, result = _post_loans8_offer(handoff, loans8_base_url)
                if not ok:
                    print(MAIN_HANDOFF_ERROR_TEMPLATE.format(error=result))
                else:
                    print("\nWorkflow 2 response:\n")
                    print(json.dumps(result, indent=2))
                    print(MAIN_HANDOFF_SUCCESS)
            except Exception as exc:
                print(MAIN_VALIDATION_WARN_TEMPLATE.format(error=exc))
            break

    print_audit_trail(session_id)


if __name__ == "__main__":
    main()
