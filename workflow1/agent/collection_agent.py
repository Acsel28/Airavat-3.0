from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from workflow1.config import CONFIDENCE_THRESHOLD, REQUIRED_COLLECTED_FIELDS
from workflow1.schema import AgentState, LLMInferenceOutput, Phase1Output, PolicyInputs

from workflow1.agent.extractor import get_missing_required_fields, parse_collection_response
from workflow1.agent.llm_client import invoke_llm
from workflow1.agent.prompts import (
    COLLECTION_PROMPT,
    HANDOFF_SUCCESS_MESSAGE_TEMPLATE,
    HANDOFF_VALIDATION_FAILURE_MESSAGE,
    INFER_PERSONA_PROMPT,
    SUMMARY_PROMPT,
    SYSTEM_PROMPT,
    WARMUP_PROMPT,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_recent_messages(messages: list[dict]) -> str:
    if not messages:
        return "No prior messages."
    return "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)


def _append_message(state: AgentState, role: str, content: str) -> None:
    state["messages"].append(
        {"role": role, "content": content, "timestamp": _now_iso(), "stage": state.get("stage")}
    )


def _apply_extracted_fields(state: AgentState, extracted: dict, confidence: dict) -> None:
    mapping = {
        "existing_emi_monthly": "existing_emi_monthly",
        "active_loan_count": "active_loan_count",
        "missed_payments_last_12m": "missed_payments_last_12m",
        "collateral_offered": "collateral_offered",
        "collateral_type": "collateral_type",
        "collateral_value": "collateral_value",
        "primary_bank": "primary_bank",
        "loan_query_free_text": "loan_query_free_text",
        "requested_amount": "requested_amount",
        "preferred_tenure_months": "preferred_tenure_months",
        "urgency": "urgency",
    }

    for field, value in extracted.items():
        if field not in mapping:
            continue
        score = float(confidence.get(field, 0.0))
        state["field_confidence"][field] = score
        retries = state["retry_counts"].get(field, 0)
        if score < CONFIDENCE_THRESHOLD:
            state["retry_counts"][field] = retries + 1
            if retries >= 1:
                state[mapping[field]] = value
            continue
        state[mapping[field]] = value


def _should_skip_collateral_details(state: AgentState) -> bool:
    offered = state.get("collateral_offered")
    return offered is False


def _pre_phase1_summary(state: AgentState) -> str:
    return (
        f"Name: {state.get('full_name')}, Employer: {state.get('employer_name')}, "
        f"Net income: ₹{state.get('net_monthly_income')}"
    )


def _collected_summary(state: AgentState) -> str:
    parts = []
    for key in [
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
    ]:
        value = state.get(key)
        if value is not None:
            parts.append(f"{key}: {value}")
    return ", ".join(parts) if parts else "none"


def _pending_fields(state: AgentState) -> list[str]:
    pending = [f for f in REQUIRED_COLLECTED_FIELDS if state.get(f) is None]
    if state.get("collateral_offered") is True:
        for field in ["collateral_type", "collateral_value"]:
            if state.get(field) is None:
                pending.append(field)
    for field in ["primary_bank", "preferred_tenure_months"]:
        if state.get(field) is None:
            pending.append(field)
    return list(dict.fromkeys(pending))


def _summarize_older_messages(messages: list[dict], keep_last: int = 10) -> str:
    if len(messages) <= keep_last:
        return ""
    older = messages[:-keep_last]
    text = " ".join(m.get("content", "") for m in older)
    text = " ".join(text.split())
    if len(text) > 600:
        text = text[:600] + "..."
    return f"Earlier in conversation: {text}"


def check_preconditions(state: AgentState) -> AgentState:
    state["stage"] = "warmup"
    required = [
        "full_name",
        "dob",
        "age",
        "gender",
        "pan",
        "city",
        "state",
        "kyc_verified",
        "employer_name",
        "employment_type",
        "gross_monthly_income",
        "net_monthly_income",
        "pf_deducted",
    ]
    missing_pre = [field for field in required if state.get(field) is None]
    if missing_pre:
        raise ValueError(f"Missing pre_phase1 fields: {', '.join(missing_pre)}")
    return state


def warmup_node(state: AgentState) -> AgentState:
    state["stage"] = "warmup"
    if any(m.get("role") == "user" for m in state.get("messages", [])):
        return state
    last_user = next((m for m in reversed(state.get("messages", [])) if m.get("role") == "user"), None)
    if last_user:
        content = str(last_user.get("content", "")).lower()
        if "urgent" in content or "asap" in content or "immediate" in content:
            state["urgency"] = "immediate"
        elif "within" in content and "month" in content:
            state["urgency"] = "within_month"
        elif "planning" in content or "flexible" in content:
            state["urgency"] = "flexible"

        if "first time" in content or "never" in content or "not before" in content:
            state["risk_persona"] = "first_time"

    if state.get("warmup_turns_done", 0) >= 2:
        return state

    prompt = WARMUP_PROMPT.format(
        full_name=state.get("full_name"),
        employer_name=state.get("employer_name"),
        net_monthly_income=state.get("net_monthly_income"),
    )
    response = invoke_llm(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    reply = str(response.content).strip()
    if reply:
        _append_message(state, "assistant", reply)
    state["warmup_turns_done"] = state.get("warmup_turns_done", 0) + 1
    return state


def collection_node(state: AgentState) -> AgentState:
    state["stage"] = "collection"
    state["turn_number"] = int(state.get("turn_number", 0)) + 1
    last_messages = state.get("messages", [])[-6:]
    prompt = COLLECTION_PROMPT.format(
        pre_phase1_summary=_pre_phase1_summary(state),
        collected_fields_summary=_collected_summary(state),
        pending_fields=", ".join(_pending_fields(state)),
        low_confidence_flags=", ".join(state.get("low_confidence_flags", [])),
        last_6_messages=_format_recent_messages(last_messages),
    )
    response = invoke_llm(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    raw = str(response.content).strip()
    spoken, extracted = parse_collection_response(raw)
    if spoken:
        _append_message(state, "assistant", spoken)

    if extracted is None:
        return state

    _apply_extracted_fields(state, extracted.extracted_fields, extracted.confidence_scores)

    low_conf = [
        field
        for field, score in extracted.confidence_scores.items()
        if float(score) < CONFIDENCE_THRESHOLD
    ]
    state["low_confidence_flags"] = low_conf
    state["pending_clarifications"] = low_conf
    return state


def compute_derived_fields(state: AgentState) -> AgentState:
    state["stage"] = "computing"
    try:
        foir_current = float(state["existing_emi_monthly"] or 0) / float(state["net_monthly_income"])
    except Exception:
        foir_current = 0.0

    max_eligible_emi = int(state["net_monthly_income"] * 0.55) - int(state["existing_emi_monthly"] or 0)

    r = 0.12 / 12 / 100
    n = 120
    try:
        max_eligible_amount_approx = int(max_eligible_emi * ((1 + r) ** n - 1) / (r * (1 + r) ** n))
    except Exception:
        max_eligible_amount_approx = 0

    payment_score = 100 - int(state["missed_payments_last_12m"] or 0) * 15
    payment_score = max(0, payment_score)

    utilisation_ratio = 0.0
    if state["net_monthly_income"]:
        utilisation_ratio = float(state["existing_emi_monthly"] or 0) / float(state["net_monthly_income"])

    if utilisation_ratio <= 0.30:
        utilisation_score = 100
    elif utilisation_ratio <= 0.50:
        utilisation_score = 70
    elif utilisation_ratio <= 0.70:
        utilisation_score = 40
    else:
        utilisation_score = 10

    lc = int(state["active_loan_count"] or 0)
    if lc == 0:
        mix_score = 60
    elif lc <= 2:
        mix_score = 100
    elif lc <= 4:
        mix_score = 80
    else:
        mix_score = 50

    urgency_map = {"flexible": 100, "within_month": 70, "immediate": 40}
    enquiry_score = urgency_map.get(state.get("urgency"), 70)

    collateral_score = 100 if state.get("collateral_offered") else 50

    raw = (
        payment_score * 0.35
        + utilisation_score * 0.30
        + mix_score * 0.15
        + enquiry_score * 0.10
        + collateral_score * 0.10
    )

    computed_credit_score = int(300 + round(raw * 6.0))
    computed_credit_score = max(300, min(900, computed_credit_score))

    fraud_score = 0
    liveness_estimated_age = state.get("age", 0)
    if state.get("age", 0) - liveness_estimated_age > 5:
        fraud_score += 30
    if state.get("transcript_contradiction_flag"):
        fraud_score += 25
    if int(state.get("active_loan_count") or 0) > 4:
        fraud_score += 15
    if foir_current > 0.70:
        fraud_score += 10
    computed_fraud_score = min(100, fraud_score)

    state["credit_score"] = computed_credit_score
    state["fraud_score"] = computed_fraud_score
    state["foir_current"] = round(foir_current, 4)
    state["max_eligible_emi"] = max_eligible_emi
    state["max_eligible_amount_approx"] = max_eligible_amount_approx
    state["age_kyc_delta"] = 0
    state["phase1_completed_at"] = _now_iso()
    state["phase1_complete"] = True

    return state


def infer_persona_node(state: AgentState) -> AgentState:
    state["stage"] = "computing"
    full_messages = state.get("messages", [])
    older_summary = _summarize_older_messages(full_messages)
    recent = full_messages[-10:]
    convo = "\n".join(
        [older_summary] + [f"{m.get('role')}: {m.get('content')}" for m in recent if m]
    ).strip()
    collected = _collected_summary(state)
    prompt = INFER_PERSONA_PROMPT.format(
        full_conversation=convo,
        all_collected_fields=collected,
    )
    response = invoke_llm([
        {"role": "user", "content": prompt},
    ], temperature=0.2)
    raw = str(response.content).strip()
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```"))
    try:
        data = json.loads(raw)
        parsed = LLMInferenceOutput(**data)
    except Exception:
        parsed = LLMInferenceOutput(
            intent_category=None,
            intent_confidence=0.0,
            risk_persona="standard",
            transcript_contradiction_flag=False,
        )

    intent_category = parsed.intent_category if parsed.intent_category in {
        "home_purchase",
        "home_improvement",
        "education",
        "medical",
        "vehicle",
        "business",
        "debt_consolidation",
        "personal",
    } else None
    intent_confidence = parsed.intent_confidence if parsed.intent_confidence is not None else 0.0
    risk_persona = parsed.risk_persona if parsed.risk_persona in {
        "conservative",
        "standard",
        "first_time",
        "distressed",
    } else "standard"

    state["intent_category"] = intent_category
    state["intent_confidence"] = float(intent_confidence)
    state["risk_persona"] = risk_persona
    state["transcript_contradiction_flag"] = bool(parsed.transcript_contradiction_flag)
    return state


def summary_node(state: AgentState) -> AgentState:
    state["stage"] = "complete"
    prompt = SUMMARY_PROMPT.format(
        full_name=state.get("full_name"),
        loan_query_free_text=state.get("loan_query_free_text"),
        requested_amount=state.get("requested_amount"),
        preferred_tenure_months=state.get("preferred_tenure_months") or "flexible",
        credit_score=state.get("credit_score"),
    )
    response = invoke_llm([
        {"role": "user", "content": prompt},
    ], temperature=0.3)
    reply = str(response.content).strip()
    if reply:
        _append_message(state, "assistant", reply)
    state["phase1_complete"] = True
    return state


def route_after_warmup(state: AgentState) -> Literal["collection_node", "await_user"]:
    has_user = any(m.get("role") == "user" for m in state.get("messages", []))
    if not has_user:
        return "await_user"
    return "collection_node"


def route_after_collection(state: AgentState) -> Literal["compute_derived_fields", "await_user"]:
    missing = get_missing_required_fields(state)
    low_conf = state.get("low_confidence_flags", [])
    unresolved = [f for f in low_conf if state.get("retry_counts", {}).get(f, 0) < 2]
    if not missing and not unresolved:
        return "compute_derived_fields"
    return "await_user"


def await_user_node(state: AgentState) -> AgentState:
    state["stage"] = "await_user"
    return state


def build_phase1_output(state: AgentState) -> Phase1Output:
    return Phase1Output(
        session_id=state["session_id"],
        query=str(state.get("loan_query_free_text") or ""),
        policy_inputs=PolicyInputs(
            age=state["age"],
            employment_type=state["employment_type"],
            gross_monthly_income=state["gross_monthly_income"],
            net_monthly_income=state["net_monthly_income"],
            existing_emi_monthly=int(state.get("existing_emi_monthly") or 0),
            credit_score=int(state.get("credit_score") or 0),
            fraud_score=int(state.get("fraud_score") or 0),
            risk_persona=str(state.get("risk_persona") or "standard"),
            intent_category=state.get("intent_category"),
            requested_amount=int(state.get("requested_amount") or 0),
            preferred_tenure_months=state.get("preferred_tenure_months"),
            collateral_offered=bool(state.get("collateral_offered")),
            collateral_value=state.get("collateral_value"),
            missed_payments_last_12m=int(state.get("missed_payments_last_12m") or 0),
        ),
    )


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("check_preconditions", check_preconditions)
    graph.add_node("warmup_node", warmup_node)
    graph.add_node("collection_node", collection_node)
    graph.add_node("compute_derived_fields", compute_derived_fields)
    graph.add_node("infer_persona", infer_persona_node)
    graph.add_node("summary_node", summary_node)
    graph.add_node("await_user", await_user_node)
    graph.set_entry_point("check_preconditions")
    graph.add_edge("check_preconditions", "warmup_node")
    graph.add_conditional_edges(
        "warmup_node",
        route_after_warmup,
        {"await_user": "await_user", "collection_node": "collection_node"},
    )
    graph.add_conditional_edges(
        "collection_node",
        route_after_collection,
        {"await_user": "await_user", "compute_derived_fields": "compute_derived_fields"},
    )
    graph.add_edge("await_user", END)
    graph.add_edge("compute_derived_fields", "infer_persona")
    graph.add_edge("infer_persona", "summary_node")
    graph.add_edge("summary_node", END)
    conn = sqlite3.connect("audit.db", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    return graph.compile(checkpointer=checkpointer)


agent_graph = _build_graph()
