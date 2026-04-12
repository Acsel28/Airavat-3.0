"""
AgentFinance — Full Demo Entry Point
Runs workflow1 (Phase 1 collection) then loans8 (Phase 2 offer + negotiation)
as a single terminal session.
"""

from __future__ import annotations

from typing import Any

from bridge import phase1_to_offer_request
from loans8.agent.negotiation_agent import acceptance_message
from loans8.api.dependencies import ensure_db_ready
from loans8.api.schemas import ConcessionTracker, LoanProduct, NegotiationState, OfferTerms
from loans8.api.services.session_store import init_session_store
from loans8.engine.runner import accept_offer, generate_loan_offer, run_negotiation_turn, search_loans
from workflow1.main import run_phase1


def _format_inr(value: int | None) -> str:
    if value is None:
        return "₹0"
    digits = str(int(value))
    if len(digits) <= 3:
        return f"₹{digits}"
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return f"₹{','.join(parts + [tail])}"


def _prompt_yes_no(prompt: str) -> bool:
    while True:
        raw = input(prompt).strip().lower()
        if raw in {"yes", "y"}:
            return True
        if raw in {"no", "n"}:
            return False
        print("Please type 'yes' or 'no'.")


def _print_phase1_summary(phase1_result: dict) -> None:
    policy = phase1_result.get("policy_inputs", {})
    loan_purpose = phase1_result.get("query") or ""
    amount = _format_inr(policy.get("requested_amount"))
    tenure = policy.get("preferred_tenure_months")
    tenure_text = f"{tenure} months" if tenure else "flexible"
    existing_emi = _format_inr(policy.get("existing_emi_monthly"))
    credit_score = policy.get("credit_score") or 0
    risk_persona = policy.get("risk_persona") or "standard"
    persona_map = {
        "distressed": "Distressed borrower",
        "first_time": "First-time borrower",
        "conservative": "Conservative borrower",
        "standard": "Standard borrower",
    }
    risk_text = persona_map.get(risk_persona, "Standard borrower")

    print("═══════════════════════════════════════")
    print("  PROFILE SUMMARY — Please Confirm")
    print("═══════════════════════════════════════")
    print(f"  Loan purpose : {loan_purpose}")
    print(f"  Amount       : {amount}")
    print(f"  Tenure       : {tenure_text}")
    print(f"  Monthly EMIs : {existing_emi} existing")
    print(f"  Credit score : {credit_score} (computed)")
    print(f"  Risk profile : {risk_text}")
    print("═══════════════════════════════════════")


def _select_loan(top_3: list[dict]) -> int:
    while True:
        choice = input("Which loan would you like to explore? Enter 1, 2, or 3: ").strip()
        try:
            value = int(choice)
            if value in {1, 2, 3} and value <= len(top_3):
                return value
        except ValueError:
            pass


def _print_top_3(top_3: list[dict]) -> None:
    for idx, loan_dict in enumerate(top_3, 1):
        loan = LoanProduct.model_validate(loan_dict)
        terms = loan.product_terms
        line = (
            f"  {idx}. {loan.loan_name} — {_format_inr(terms.min_amount)} to {_format_inr(terms.max_amount)} "
            f"| Rate: {terms.base_interest_rate_annual:.2f}% | Max tenure: {terms.max_tenure_months} months"
        )
        print(line)


def _print_offer(offer: dict) -> None:
    terms = offer.get("offer", {})
    rate = terms.get("interest_rate_annual") or 0.0
    print("═══════════════════════════════════════")
    print("  YOUR LOAN OFFER")
    print("═══════════════════════════════════════")
    print(f"  Approved amount : {_format_inr(terms.get('approved_amount'))}")
    print(f"  Monthly EMI     : {_format_inr(terms.get('emi_monthly'))}")
    print(f"  Tenure          : {terms.get('tenure_months')} months")
    print(f"  Interest rate   : {rate:.2f}% p.a.")
    print(f"  Processing fee  : {_format_inr(terms.get('processing_fee_amount'))}")
    print(f"  Total payable   : {_format_inr(terms.get('total_payable'))}")
    print("═══════════════════════════════════════")


def _prompt_accept_or_negotiate() -> str:
    while True:
        choice = input("Would you like to accept this offer or negotiate? (accept/negotiate): ").strip().lower()
        if choice in {"accept", "negotiate"}:
            return choice


def main() -> None:
    ensure_db_ready()
    init_session_store()

    while True:
        phase1_result = run_phase1()
        if not phase1_result:
            print("Phase 1 ended without a completed profile.")
            return

        _print_phase1_summary(phase1_result)
        if _prompt_yes_no("Is this correct? Type 'yes' to proceed or 'no' to restart: "):
            break

    offer_request = phase1_to_offer_request(phase1_result)

    result = search_loans(offer_request)
    pre_eligibility = result.get("pre_eligibility") or {}
    if not pre_eligibility.get("passed", False):
        reason = pre_eligibility.get("rejection_reason") or "Not eligible"
        print(f"Pre-eligibility failed: {reason}")
        return

    top_3 = result.get("top_3", [])
    if not top_3:
        print("No eligible loan products found for your profile. A specialist will contact you.")
        return

    _print_top_3(top_3)
    choice = _select_loan(top_3)

    offer = generate_loan_offer(offer_request, choice)
    _print_offer(offer)

    action = _prompt_accept_or_negotiate()

    selected_loan = LoanProduct.model_validate(top_3[choice - 1])
    offer_terms = OfferTerms.model_validate(offer.get("offer", {}))
    negotiation_state = NegotiationState(
        session_id=offer_request["session_id"],
        loan_id=selected_loan.loan_id,
        rounds_elapsed=0,
        max_rounds=8,
        status="active",
        hard_limits=selected_loan.negotiation_limits.model_dump(),
        current_offer=offer_terms,
        concession_tracker=ConcessionTracker(),
        conversion_probability=0.5,
        recommended_next_concession=None,
        round_log=[],
    )

    if action == "accept":
        consent = accept_offer(
            negotiation_state={
                **negotiation_state.model_dump(),
                "loan": selected_loan.model_dump(),
                "policy_inputs": offer_request["policy_inputs"],
                "initial_offer": offer.get("offer", {}),
            },
            user_utterance="I accept this offer.",
        )
        message = acceptance_message(offer_terms)
        print(message)
        print(f"Consent timestamp: {consent.get('timestamp')}")
        print(f"Consent hash: {consent.get('transcript_hash')}")
        print("Session complete.")
        return

    state_payload: dict[str, Any] = {
        **negotiation_state.model_dump(),
        "loan": selected_loan.model_dump(),
        "policy_inputs": offer_request["policy_inputs"],
        "initial_offer": offer.get("offer", {}),
    }

    while True:
        current = state_payload.get("current_offer") or {}
        _print_offer({"offer": current})
        user_utterance = input("Your message: ").strip()
        if not user_utterance:
            continue

        result = run_negotiation_turn(state_payload, user_utterance)
        print(result.get("agent_message", ""))

        status = result.get("status")
        updated_state = result.get("updated_state") or {}
        state_payload = {
            **updated_state,
            "loan": selected_loan.model_dump(),
            "policy_inputs": offer_request["policy_inputs"],
            "initial_offer": offer,
        }

        if status == "accepted":
            consent = accept_offer(state_payload, "I accept this offer.")
            print(f"Consent timestamp: {consent.get('timestamp')}")
            print(f"Consent hash: {consent.get('transcript_hash')}")
            print("Session complete.")
            return
        if status == "escalated":
            print("Session complete.")
            return


if __name__ == "__main__":
    main()
