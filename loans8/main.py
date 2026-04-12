"""Tier 8 Demo — run: python main.py"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import chromadb
from dotenv import load_dotenv

import langsmith_setup
from loans8.agent.negotiation_agent import run_negotiation_turn
from loans8.agent.prompts import (
    APP_HEADER,
    MSG_DATA_NOT_READY,
    MSG_DATA_NOT_READY_CMD,
    MSG_INVALID_LOAN_CHOICE,
    MSG_NO_RESULTS,
    MSG_TOP_MATCHES,
)
from loans8.agent.retrieval import get_loan_recommendations
from loans8.api.schemas import ConcessionTracker, LoanProduct, NegotiationState, PolicyInputs
from loans8.db.setup_chroma import setup_chroma
from loans8.db.setup_sqlite import setup_sqlite
from loans8.engine.consent import capture_consent_event
from loans8.engine.eligibility import run_pre_eligibility_gate
from loans8.engine.filter import hard_filter_loans
from loans8.engine.offer_engine import generate_offer
from loans8.engine.ranker import rerank_loans

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "tier8.db"
CHROMA_PATH = BASE_DIR / "chroma_store"
COLLECTION_NAME = "loan_catalog"

TEST_POLICY = {
    "session_id": "test-session-001",
    "query": "",
    "loan_choice_index": None,
    "policy_inputs": {
        "age": 38,
        "employment_type": "salaried",
        "gross_monthly_income": 95000,
        "net_monthly_income": 78000,
        "existing_emi_monthly": 8000,
        "credit_score": 720,
        "fraud_score": 10,
        "risk_persona": "distressed",
        "intent_category": "medical",
        "requested_amount": 500000,
        "preferred_tenure_months": 36,
        "collateral_offered": False,
        "collateral_value": None,
        "missed_payments_last_12m": 0,
    },
    "negotiate": False,
    "negotiation_inputs": [],
}


def _fmt_inr(value: int) -> str:
    return f"₹{int(value):,}"


def _is_data_ready() -> bool:
    if not DB_PATH.exists():
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        loan_count = conn.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
    except sqlite3.Error:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if int(loan_count) < 18:
        return False

    try:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = client.get_collection(COLLECTION_NAME)
        ids = collection.get(include=[]).get("ids", [])
    except Exception:
        return False

    return len(set(ids)) >= 18


def _run_setup() -> None:
    setup_sqlite()
    setup_chroma()


def _print_top_3(ranked: list[LoanProduct]) -> None:
    print(MSG_TOP_MATCHES)
    for i, loan in enumerate(ranked[:3], 1):
        terms = loan.product_terms
        line = (
            f"  {i}. {loan.loan_name} — { _fmt_inr(terms.min_amount) } to { _fmt_inr(terms.max_amount) } "
            f"| Rate: {terms.base_interest_rate_annual:.2f}% | Max tenure: {terms.max_tenure_months} months"
        )
        print(line)


def _select_loan(ranked: list[LoanProduct]) -> LoanProduct:
    while True:
        choice = input("Enter 1, 2, or 3 to select a loan: ").strip()
        try:
            idx = int(choice)
            if idx in {1, 2, 3} and idx <= len(ranked):
                return ranked[idx - 1]
        except ValueError:
            pass
        print(MSG_INVALID_LOAN_CHOICE)


def _print_offer(offer) -> None:
    terms = offer.offer
    print("\n=== OFFER GENERATED ===")
    print(f"  Approved amount : {_fmt_inr(terms.approved_amount)}")
    print(f"  Monthly EMI     : {_fmt_inr(terms.emi_monthly)}")
    print(f"  Tenure          : {terms.tenure_months} months")
    print(f"  Interest rate   : {terms.interest_rate_annual:.2f}% p.a.")
    print(f"  Processing fee  : {_fmt_inr(terms.processing_fee_amount)}")


def _accept_or_negotiate() -> str:
    while True:
        choice = input("Do you want to accept or negotiate? (accept/negotiate): ").strip().lower()
        if choice in {"accept", "negotiate"}:
            return choice


def _run_negotiation_loop(
    session_id: str,
    loan: LoanProduct,
    policy: PolicyInputs,
    initial_offer,
) -> None:
    negotiation_state = NegotiationState(
        session_id=session_id,
        loan_id=loan.loan_id,
        rounds_elapsed=0,
        max_rounds=8,
        status="active",
        hard_limits=loan.negotiation_limits.model_dump(),
        current_offer=initial_offer,
        concession_tracker=ConcessionTracker(),
        conversion_probability=0.5,
        recommended_next_concession=None,
        round_log=[],
    )

    while negotiation_state.status == "active":
        offer = negotiation_state.current_offer
        print(f"\nCurrent offer: {_fmt_inr(offer.approved_amount)} | EMI {_fmt_inr(offer.emi_monthly)}")
        user_utterance = input("Your message: ").strip()
        if not user_utterance:
            continue
        negotiation_state, agent_message, consent = run_negotiation_turn(
            negotiation_state=negotiation_state,
            loan=loan,
            policy=policy,
            customer_utterance=user_utterance,
            initial_offer=initial_offer,
        )
        print(agent_message)

        if negotiation_state.status == "accepted":
            if consent:
                print("\nConsent record:\n")
                print(consent)
            return
        if negotiation_state.status == "escalated":
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Tier 8 Loan Offer & Negotiation Agent")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run one-time SQLite + Chroma setup before starting.",
    )
    args = parser.parse_args()

    print(APP_HEADER)

    load_dotenv()
    langsmith_setup.bootstrap()

    if args.setup:
        _run_setup()
    elif not _is_data_ready():
        print(MSG_DATA_NOT_READY)
        print(MSG_DATA_NOT_READY_CMD)
        return

    session_id = TEST_POLICY["session_id"]
    print(f"Session ID: {session_id}\n")

    query = input("Describe what you need a loan for: ").strip()
    if not query:
        print("No query entered. Exiting.")
        return
    TEST_POLICY["query"] = query
    policy_inputs = PolicyInputs(**TEST_POLICY["policy_inputs"])
    pre_eligibility = run_pre_eligibility_gate(policy_inputs)
    if not pre_eligibility.passed:
        print(f"Pre-eligibility failed: {pre_eligibility.rejection_reason}")
        return

    reco = get_loan_recommendations(query, top_k=6)
    if not reco.get("results"):
        print(MSG_NO_RESULTS)
        return

    loan_products: list[LoanProduct] = []
    for loan in reco["results"]:
        try:
            loan_products.append(LoanProduct.model_validate(loan))
        except Exception:
            continue

    filtered = hard_filter_loans(loan_products, policy_inputs, pre_eligibility)
    if not filtered:
        print("No eligible loan products found for your profile. A specialist will contact you.")
        return

    ranked = rerank_loans(filtered, policy_inputs)
    if not ranked:
        print("No eligible loan products found for your profile. A specialist will contact you.")
        return

    _print_top_3(ranked)
    selected_loan = _select_loan(ranked)

    offer = generate_offer(
        loan=selected_loan,
        policy=policy_inputs,
        pre_eligibility=pre_eligibility,
        session_id=session_id,
    )

    _print_offer(offer)

    next_step = _accept_or_negotiate()
    if next_step == "accept":
        consent = capture_consent_event(
            session_id=session_id,
            event_type="final_offer",
            transcript_segment="I accept this offer.",
            offer_snapshot=offer.model_dump(),
        )
        print("\nConsent record:\n")
        print(consent)
        return

    _run_negotiation_loop(
        session_id=session_id,
        loan=selected_loan,
        policy=policy_inputs,
        initial_offer=offer.offer,
    )


if __name__ == "__main__":
    main()
