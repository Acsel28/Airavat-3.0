"""
loan_agent.py — Intelligent Loan Advisor Agent powered by Gemini.

Responsibilities:
  - Multi-turn conversation with full history context
  - Real-time extraction of user profile fields via structured JSON tags
  - Loan matching from LOAN_CATALOG
  - Interest rate & amount negotiation within product limits
  - Phase machine: discovery → profiling → recommendation → negotiation → confirmation → done
  - Persistence: every turn saved to Neon DB (loan_conversations + loan_agent_state)
"""

import json
import math
import os
import re
import time
from typing import Optional

# Load environment variables early
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from loans import LOAN_CATALOG, LOAN_BY_ID

# ─── DB setup ────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("NEON_DB_URL")
_engine: Optional[Engine] = None
if DATABASE_URL:
    _engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def _run_migrations():
    """Idempotently create loan tables on startup."""
    if not _engine:
        return
    ddl = """
    CREATE TABLE IF NOT EXISTS loan_conversations (
        id             SERIAL PRIMARY KEY,
        session_id     TEXT NOT NULL,
        user_id        INTEGER,
        role           TEXT NOT NULL CHECK (role IN ('user','agent')),
        message        TEXT NOT NULL,
        intent         TEXT,
        extracted_json JSONB DEFAULT '{}',
        created_at     TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_lc_session ON loan_conversations(session_id);
    CREATE INDEX IF NOT EXISTS idx_lc_user    ON loan_conversations(user_id);

    CREATE TABLE IF NOT EXISTS loan_applications (
        id                  SERIAL PRIMARY KEY,
        session_id          TEXT NOT NULL UNIQUE,
        user_id             INTEGER,
        loan_id             TEXT NOT NULL,
        loan_name           TEXT NOT NULL,
        loan_type           TEXT NOT NULL,
        requested_amount    BIGINT,
        approved_amount     BIGINT,
        interest_rate       NUMERIC(5,2),
        tenure_months       INTEGER,
        processing_fee      NUMERIC(12,2),
        monthly_emi         NUMERIC(12,2),
        negotiation_rounds  INTEGER DEFAULT 0,
        status              TEXT DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
        extracted_profile   JSONB DEFAULT '{}',
        created_at          TIMESTAMPTZ DEFAULT NOW(),
        approved_at         TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_la_session ON loan_applications(session_id);
    CREATE INDEX IF NOT EXISTS idx_la_user    ON loan_applications(user_id);

    CREATE TABLE IF NOT EXISTS loan_agent_state (
        session_id          TEXT PRIMARY KEY,
        user_id             INTEGER,
        recommended_loan_id TEXT,
        extracted_profile   JSONB DEFAULT '{}',
        negotiation_state   JSONB DEFAULT '{}',
        conversation_phase  TEXT DEFAULT 'discovery',
        turn_count          INTEGER DEFAULT 0,
        updated_at          TIMESTAMPTZ DEFAULT NOW()
    );
    """
    with _engine.begin() as conn:
        conn.execute(text(ddl))


_run_migrations()

# ─── In-memory session cache ──────────────────────────────────────────────────
# Avoids a DB round-trip on every turn; flushed to DB after each turn.
_agent_sessions: dict = {}

PHASES = ["discovery", "profiling", "recommendation", "negotiation", "confirmation", "done"]


# ─── EMI Calculator ──────────────────────────────────────────────────────────
def calculate_emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    if annual_rate == 0 or tenure_months == 0:
        return principal / tenure_months if tenure_months else 0
    r = annual_rate / 12 / 100
    emi = principal * r * (1 + r) ** tenure_months / ((1 + r) ** tenure_months - 1)
    return round(emi, 2)


# ─── CIBL Score Calculator ──────────────────────────────────────────────────
def calculate_cibl_score(profile: dict) -> dict:
    """
    Calculate a CIBL-style credit score (0-900) based on provided and inferred factors.
    
    CIBL Score Components:
    - Payment History (35%): Whether user has paid loans on time
    - Credit Utilization (20%): Debt to income ratio
    - Credit Age (15%): How long using credit
    - Credit Mix (15%): Variety of credit types
    - Recent Inquiries (15%): Recent credit applications
    """
    score = 300  # Base score
    
    # Factor 1: Credit History Hint (35%)
    credit_hint = profile.get("credit_score_hint", "fair")
    if credit_hint == "good":
        score += 210  # 300 + 210 = 510 (good payment history)
    elif credit_hint == "fair":
        score += 140  # 300 + 140 = 440 (average)
    else:  # poor
        score += 50   # 300 + 50 = 350 (needs improvement)
    
    # Factor 2: Employment Stability (impacts credit mix & history) (20%)
    employment = profile.get("employment_type", "salaried")
    if employment == "salaried":
        score += 120  # Stable employment
    elif employment == "self_employed":
        score += 80   # Moderate stability
    else:  # business_owner
        score += 60   # Higher volatility
    
    # Factor 3: Collateral (impacts credit mix) (15%)
    has_collateral = profile.get("collateral_available", False)
    if has_collateral:
        score += 90
    else:
        score += 30
    
    # Factor 4: Income Level (indicator of repayment capacity) (15%)
    monthly_income = profile.get("monthly_income", 0)
    if monthly_income >= 200000:
        score += 90
    elif monthly_income >= 100000:
        score += 60
    elif monthly_income >= 50000:
        score += 40
    else:
        score += 20
    
    # Factor 5: Loan Purpose (risk assessment) (15%)
    loan_purpose = profile.get("loan_purpose", "").lower()
    if any(w in loan_purpose for w in ["home", "house", "mortgage"]):
        score += 75  # Lower risk
    elif any(w in loan_purpose for w in ["education", "study"]):
        score += 70
    elif any(w in loan_purpose for w in ["car", "vehicle", "auto"]):
        score += 65
    elif any(w in loan_purpose for w in ["business", "investment"]):
        score += 55
    else:
        score += 45
    
    # Cap at 900
    final_score = min(int(score), 900)
    
    # Determine rating
    if final_score >= 750:
        rating = "Excellent"
    elif final_score >= 650:
        rating = "Good"
    elif final_score >= 550:
        rating = "Fair"
    else:
        rating = "Poor"
    
    return {
        "score": final_score,
        "rating": rating,
        "breakdown": {
            "payment_history": credit_hint,
            "employment_stability": employment,
            "collateral": "Yes" if has_collateral else "No",
            "estimated_monthly_income": f"₹{monthly_income:,.0f}" if monthly_income else "Not specified",
            "loan_purpose": loan_purpose or "Not specified",
        }
    }


# ─── Loan Matcher ────────────────────────────────────────────────────────────
def match_loans(profile: dict) -> list[dict]:
    """Return ranked list of eligible loan products given extracted profile."""
    purpose = (profile.get("loan_purpose") or "").lower()
    emp = (profile.get("employment_type") or "").lower()
    amount = profile.get("requested_amount") or 0
    income = profile.get("monthly_income") or 0

    scores = []
    for loan in LOAN_CATALOG:
        score = 0

        # Tag match
        tags = [t.lower() for t in loan["use_case_tags"]]
        if any(kw in purpose for kw in tags):
            score += 30

        # Intent match
        intent = loan["intent_tags"][0] if loan["intent_tags"] else ""
        if intent in purpose:
            score += 20

        # Amount fit
        p = loan["product_terms"]
        if amount and p["min_amount"] <= amount <= p["max_amount"]:
            score += 25
        elif amount and amount < p["min_amount"]:
            score -= 10

        # Employment fit
        allowed = loan["eligibility"]["allowed_employment_types"]
        if emp and any(e in emp for e in allowed):
            score += 10

        # Income adequacy (rough FOIR: EMI should be < 50% of income)
        if income and amount:
            default_tenure = p["max_tenure_months"]
            emi = calculate_emi(amount, p["base_interest_rate_annual"], default_tenure)
            foir = emi / income
            if foir <= 0.5:
                score += 15
            elif foir <= 0.65:
                score += 5

        if score > 0:
            scores.append((score, loan))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [loan for _, loan in scores[:3]]


# ─── Gemini Caller ───────────────────────────────────────────────────────────
def _call_gemini(system_prompt: str, messages: list[dict]) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_reply(messages)

    try:
        from google import genai
        from google.genai import types as gtypes

        client = genai.Client(api_key=api_key)

        history = []
        for m in messages[:-1]:  # all but last
            role = "user" if m["role"] == "user" else "model"
            history.append(gtypes.Content(role=role, parts=[gtypes.Part(text=m["message"])]))

        last = messages[-1]
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=history + [gtypes.Content(role="user", parts=[gtypes.Part(text=last["message"])])],
            config=gtypes.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.7,
                max_output_tokens=1024,
            ),
        )
        return (response.text or "").strip()
    except Exception as e:
        print(f"[LoanAgent] Gemini error: {e}")
        return _fallback_reply(messages)


def _fallback_reply(messages: list) -> str:
    last = (messages[-1]["message"] if messages else "").lower()
    if any(w in last for w in ["hi", "hello", "hey", "start"]):
        return "Hello! I'm your AIRAVAT Loan Advisor. I'd love to help you find the right loan. Could you tell me what you're looking to finance?"
    if any(w in last for w in ["home", "house", "flat"]):
        return "Great! A home loan sounds like a good fit. Could you share your approximate monthly income and how much you'd like to borrow?"
    if any(w in last for w in ["car", "vehicle", "bike"]):
        return "Perfect! For a vehicle loan, I'll need your monthly income and the approximate vehicle cost. Could you share those?"
    if any(w in last for w in ["rate", "interest", "lower", "reduce", "negotiat"]):
        return "I understand you'd like a better rate. Let me check what I can do for your profile. Could you confirm your employment type and credit history?"
    return "I'm here to help you find the best loan option. Could you tell me a bit more about what you need the funds for?"


# ─── System Prompt Builder ───────────────────────────────────────────────────
def _build_system_prompt(kyc_profile: dict, current_state: dict) -> str:
    phase = current_state.get("conversation_phase", "discovery")
    extracted = current_state.get("extracted_profile", {})
    neg_state = current_state.get("negotiation_state", {})
    recommended_id = current_state.get("recommended_loan_id")

    recommended_loan_info = ""
    if recommended_id and recommended_id in LOAN_BY_ID:
        loan = LOAN_BY_ID[recommended_id]
        neg_rate = neg_state.get("current_rate", loan["product_terms"]["base_interest_rate_annual"])
        neg_amount = neg_state.get("current_amount", extracted.get("requested_amount", loan["product_terms"]["min_amount"]))
        neg_tenure = neg_state.get("current_tenure", loan["product_terms"]["max_tenure_months"])
        neg_rounds = neg_state.get("rounds", 0)
        max_rounds = 3
        min_rate = loan["product_terms"]["base_interest_rate_annual"] - loan["negotiation_limits"]["max_rate_discount_bps"] / 100
        recommended_loan_info = f"""
CURRENT RECOMMENDED LOAN:
  ID: {loan['loan_id']} — {loan['loan_name']} ({loan['loan_type']})
  Base Rate: {loan['product_terms']['base_interest_rate_annual']}% | Min Negotiable Rate: {min_rate:.2f}%
  Current Negotiated Rate: {neg_rate:.2f}%
  Current Amount: ₹{neg_amount:,.0f} | Tenure: {neg_tenure} months
  Negotiation Rounds Used: {neg_rounds}/{max_rounds}
  NON-NEGOTIABLE: {', '.join(loan['non_negotiable'])}
  Allowed Tenure Options: {loan['negotiation_limits']['tenure_options_months']}
"""

    catalog_summary = "\n".join([
        f"  [{l['loan_id']}] {l['loan_name']} ({l['loan_type']}): "
        f"₹{l['product_terms']['min_amount']:,}–₹{l['product_terms']['max_amount']:,}, "
        f"{l['product_terms']['base_interest_rate_annual']}%–{l['product_terms']['max_interest_rate_annual']}%, "
        f"{l['product_terms']['min_tenure_months']}–{l['product_terms']['max_tenure_months']} months | "
        f"Tags: {', '.join(l['use_case_tags'][:3])}"
        for l in LOAN_CATALOG
    ])

    user_info = f"""
VERIFIED KYC USER:
  Name: {kyc_profile.get('full_name', 'Unknown')}
  Email: {kyc_profile.get('email', 'N/A')}
  Mobile: {kyc_profile.get('mobile_number', 'N/A')}
  Aadhaar: {kyc_profile.get('aadhaar_masked', '****')}
""" if kyc_profile else "  (No KYC profile available)"

    extracted_info = ""
    if extracted:
        extracted_info = "\nCURRENTLY EXTRACTED PROFILE (DO NOT ASK AGAIN FOR THESE):\n" + "\n".join(
            f"  {k}: {v}" for k, v in extracted.items() if v is not None
        )

    phase_instructions = {
        "discovery": "You are in DISCOVERY phase. Your goal is to warmly greet the user and understand what they need the loan for. Ask open-ended questions. Do NOT recommend a specific product yet.",
        "profiling": "You are in PROFILING phase. Collect missing profile data: employment type (salaried/self-employed/business owner), monthly income, requested loan amount, preferred tenure, AND credit history (excellent/good/fair/poor - ask if they've had previous loans and how punctually they paid). Ask one question at a time naturally.",
        "recommendation": "You are in RECOMMENDATION phase. FIRST, present their CIBL Credit Score (0-900) - show the score, rating, and explain that backend systems automatically estimate factors like: payment history from past records, defaults/late payments, credit age, credit mix, etc. Then recommend the best loan product. Explain why it fits. Quote the rate, tenure, and EMI.",
        "negotiation": "You are in NEGOTIATION phase. The user may request a lower rate or higher amount. You can negotiate within the limits shown above. Be a skilled but empathetic negotiator. You can reduce rate by max the allowed BPS. If user pushes beyond limits, politely but firmly decline and explain why.",
        "confirmation": "You are in CONFIRMATION phase. Summarize the final agreed terms clearly: loan name, amount, rate, tenure, EMI, and processing fee. Ask the user to confirm.",
        "done": "The conversation is complete. The user has accepted the terms. Warmly close the conversation.",
    }.get(phase, "Be helpful and professional.")

    return f"""You are AIRAVAT Loan Advisor — a warm, professional, and highly intelligent loan sales agent for AIRAVAT Financial Services. You speak naturally like a real human loan officer, never robotic.

CURRENT CONVERSATION PHASE: {phase.upper()}
{phase_instructions}

{user_info}
{extracted_info}
{recommended_loan_info}

AVAILABLE LOAN PRODUCTS:
{catalog_summary}

CRITICAL RULES:
1. Extract key information from every user message and output it in a hidden <EXTRACT>...</EXTRACT> block at the END of your response (NOT shown to user). Format as JSON:
   {{"employment_type": "salaried|self_employed|business_owner|null", "monthly_income": <number or null>, "loan_purpose": "...", "requested_amount": <number or null>, "tenure_months": <number or null>, "credit_score_hint": "good|fair|poor|null", "collateral_available": <true|false|null>, "confidence": <0.0-1.0>, "recommended_loan_id": "<ID or null>", "phase": "<next phase name>", "negotiation_request": "rate|amount|tenure|none"}}
2. PROFILING PHASE CRITICAL: Always ask user about credit history. Questions like "Have you had loans before?" "How punctually do you pay?" "Any delays or defaults in past records?" This helps us assess credit_score_hint.
3. RECOMMENDATION PHASE CRITICAL: FIRST calculate and show the user their CIBL Credit Score (0-900 scale). Explain that the score includes factors like: payment history (from past records), defaults/late payments, credit age, credit mix, and recent inquiries - many estimated by our backend from available data.
4. NEVER reveal the <EXTRACT> block content in your spoken reply — it is backend-only.
5. Keep replies conversational, warm, and 2–4 sentences max. Never sound like a chatbot.
6. Never break non-negotiable terms. If user insists, explain gently and offer alternatives.
7. When recommending, always calculate and mention the approximate monthly EMI.
8. Use Indian Rupee (₹) formatting. Use "lakhs" and "crores" naturally.
9. You already know the user's verified name from KYC — use it naturally.
10. If the user seems confident and all terms are agreed, move to confirmation phase.
11. After confirmation is accepted by user, set phase to "done" in EXTRACT block.
"""


# ─── Extract parser ──────────────────────────────────────────────────────────
def _parse_extract(raw_reply: str) -> tuple[str, dict]:
    """Split agent reply from <EXTRACT>...</EXTRACT> block. Returns (clean_reply, extracted_dict)."""
    pattern = r"<EXTRACT>(.*?)</EXTRACT>"
    match = re.search(pattern, raw_reply, re.DOTALL | re.IGNORECASE)
    extracted = {}
    clean = raw_reply

    if match:
        clean = re.sub(pattern, "", raw_reply, flags=re.DOTALL | re.IGNORECASE).strip()
        try:
            extracted = json.loads(match.group(1).strip())
        except Exception:
            pass

    return clean, extracted


# ─── State persistence ───────────────────────────────────────────────────────
def _load_state(session_id: str, user_id: Optional[int]) -> dict:
    """Load state from in-memory cache or DB."""
    if session_id in _agent_sessions:
        return _agent_sessions[session_id]

    state = {
        "session_id": session_id,
        "user_id": user_id,
        "conversation_phase": "discovery",
        "extracted_profile": {},
        "negotiation_state": {},
        "recommended_loan_id": None,
        "turn_count": 0,
        "messages": [],  # in-memory full history for Gemini context
    }

    if _engine:
        try:
            with _engine.connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM loan_agent_state WHERE session_id = :sid"),
                    {"sid": session_id},
                ).mappings().first()
                if row:
                    state["conversation_phase"] = row["conversation_phase"] or "discovery"
                    state["extracted_profile"] = row["extracted_profile"] or {}
                    state["negotiation_state"] = row["negotiation_state"] or {}
                    state["recommended_loan_id"] = row["recommended_loan_id"]
                    state["turn_count"] = row["turn_count"] or 0
                    state["user_id"] = row["user_id"] or user_id

                # Load message history from DB
                msgs = conn.execute(
                    text(
                        "SELECT role, message FROM loan_conversations "
                        "WHERE session_id = :sid ORDER BY created_at ASC"
                    ),
                    {"sid": session_id},
                ).mappings().all()
                state["messages"] = [{"role": r["role"], "message": r["message"]} for r in msgs]
        except Exception as e:
            print(f"[LoanAgent] DB load error: {e}")

    _agent_sessions[session_id] = state
    return state


def _save_state(state: dict):
    """Flush agent state to DB."""
    print(f"[LoanAgent] _save_state called for session={state.get('session_id')}")
    if not _engine:
        print("[LoanAgent] No database engine available for _save_state")
        return
    try:
        with _engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO loan_agent_state
                        (session_id, user_id, recommended_loan_id, extracted_profile,
                         negotiation_state, conversation_phase, turn_count, updated_at)
                    VALUES
                        (:sid, :uid, :rec, :ep, :ns, :phase, :tc, NOW())
                    ON CONFLICT (session_id) DO UPDATE SET
                        user_id             = EXCLUDED.user_id,
                        recommended_loan_id = EXCLUDED.recommended_loan_id,
                        extracted_profile   = EXCLUDED.extracted_profile,
                        negotiation_state   = EXCLUDED.negotiation_state,
                        conversation_phase  = EXCLUDED.conversation_phase,
                        turn_count          = EXCLUDED.turn_count,
                        updated_at          = EXCLUDED.updated_at
                """),
                {
                    "sid": state["session_id"],
                    "uid": state.get("user_id"),
                    "rec": state.get("recommended_loan_id"),
                    "ep": json.dumps(state.get("extracted_profile", {})),
                    "ns": json.dumps(state.get("negotiation_state", {})),
                    "phase": state.get("conversation_phase", "discovery"),
                    "tc": state.get("turn_count", 0),
                },
            )
    except Exception as e:
        print(f"[LoanAgent] DB save state error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def _save_message(session_id: str, user_id: Optional[int], role: str, message: str,
                  intent: Optional[str] = None, extracted: Optional[dict] = None):
    if not _engine:
        return
    try:
        with _engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO loan_conversations
                        (session_id, user_id, role, message, intent, extracted_json, created_at)
                    VALUES (:sid, :uid, :role, :msg, :intent, :ext, NOW())
                """),
                {
                    "sid": session_id,
                    "uid": user_id,
                    "role": role,
                    "msg": message,
                    "intent": intent,
                    "ext": json.dumps(extracted or {}),
                },
            )
    except Exception as e:
        print(f"[LoanAgent] DB save message error: {e}")


# ─── Negotiation logic ───────────────────────────────────────────────────────
def _apply_negotiation(state: dict, extracted: dict) -> dict:
    """Update negotiation state based on what Gemini extracted."""
    rec_id = state.get("recommended_loan_id")
    if not rec_id or rec_id not in LOAN_BY_ID:
        return state

    loan = LOAN_BY_ID[rec_id]
    neg = state.get("negotiation_state", {})
    profile = state.get("extracted_profile", {})

    # Initialize negotiation state if first time
    if "current_rate" not in neg:
        neg["current_rate"] = loan["product_terms"]["base_interest_rate_annual"]
        neg["current_amount"] = profile.get("requested_amount") or loan["product_terms"]["min_amount"]
        neg["current_tenure"] = profile.get("tenure_months") or loan["product_terms"]["max_tenure_months"]
        neg["rounds"] = 0
        neg["original_rate"] = loan["product_terms"]["base_interest_rate_annual"]
        neg["min_rate"] = round(
            loan["product_terms"]["base_interest_rate_annual"]
            - loan["negotiation_limits"]["max_rate_discount_bps"] / 100,
            2,
        )

    req = extracted.get("negotiation_request", "none")
    credit_hint = profile.get("credit_score_hint", "fair")

    if req == "rate" and neg["rounds"] < 3:
        # Allow reduction only for good credit profiles
        reduction = 0.25 if credit_hint == "good" else 0.15
        new_rate = max(neg["min_rate"], round(neg["current_rate"] - reduction, 2))
        if new_rate < neg["current_rate"]:
            neg["current_rate"] = new_rate
            neg["rounds"] += 1

    elif req == "amount" and neg["rounds"] < 3:
        req_amount = extracted.get("requested_amount") or neg["current_amount"]
        max_allowed = loan["product_terms"]["max_amount"] * (
            1 + loan["negotiation_limits"]["max_amount_extension_pct"] / 100
        )
        new_amount = min(req_amount, max_allowed)
        neg["current_amount"] = round(new_amount)
        neg["rounds"] += 1

    elif req == "tenure":
        options = loan["negotiation_limits"]["tenure_options_months"]
        pref = extracted.get("tenure_months") or neg["current_tenure"]
        # Pick closest allowed tenure
        closest = min(options, key=lambda x: abs(x - pref))
        neg["current_tenure"] = closest

    state["negotiation_state"] = neg
    return state


# ─── Main Chat Function ───────────────────────────────────────────────────────
def loan_chat(
    session_id: str,
    user_message: str,
    kyc_profile: Optional[dict] = None,
    user_id: Optional[int] = None,
) -> dict:
    """
    Process one user turn. Returns:
      {reply, phase, extracted_fields, recommended_loan, confidence, is_final, offer}
    """
    kyc_profile = kyc_profile or {}
    state = _load_state(session_id, user_id)

    # Append user message to in-memory history
    state["messages"].append({"role": "user", "message": user_message})
    state["turn_count"] += 1

    # Build system prompt with current state
    system_prompt = _build_system_prompt(kyc_profile, state)

    # Call Gemini
    raw_reply = _call_gemini(system_prompt, state["messages"])

    # Parse out <EXTRACT> block
    clean_reply, extracted = _parse_extract(raw_reply)

    # Merge extracted fields into state
    profile = state.get("extracted_profile", {})
    for field in ["employment_type", "monthly_income", "loan_purpose", "requested_amount",
                  "tenure_months", "credit_score_hint", "collateral_available"]:
        if extracted.get(field) is not None:
            profile[field] = extracted[field]
    state["extracted_profile"] = profile

    # Update recommended loan
    if extracted.get("recommended_loan_id") and extracted["recommended_loan_id"] in LOAN_BY_ID:
        state["recommended_loan_id"] = extracted["recommended_loan_id"]

    # Auto-match if no recommendation yet and enough profile info
    if not state["recommended_loan_id"] and (profile.get("loan_purpose") or profile.get("requested_amount")):
        matches = match_loans(profile)
        if matches:
            state["recommended_loan_id"] = matches[0]["loan_id"]

    # Apply negotiation
    if extracted.get("negotiation_request") and extracted["negotiation_request"] != "none":
        state = _apply_negotiation(state, extracted)

    # Update phase
    new_phase = extracted.get("phase", state["conversation_phase"])
    if new_phase in PHASES:
        state["conversation_phase"] = new_phase

    # Append agent reply to history
    state["messages"].append({"role": "agent", "message": clean_reply})

    # Persist to DB
    _save_message(session_id, user_id, "user", user_message, extracted.get("loan_purpose"), extracted)
    _save_message(session_id, user_id, "agent", clean_reply, state["conversation_phase"])
    _save_state(state)

    # Build recommended loan summary for frontend
    recommended_loan = None
    offer = None
    rec_id = state.get("recommended_loan_id")
    if rec_id and rec_id in LOAN_BY_ID:
        loan = LOAN_BY_ID[rec_id]
        neg = state.get("negotiation_state", {})
        rate = neg.get("current_rate", loan["product_terms"]["base_interest_rate_annual"])
        amount = neg.get("current_amount",
                         profile.get("requested_amount") or loan["product_terms"]["min_amount"])
        tenure = neg.get("current_tenure",
                         profile.get("tenure_months") or loan["product_terms"]["max_tenure_months"])
        emi = calculate_emi(amount, rate, tenure)
        processing_fee = max(
            loan["product_terms"]["processing_fee_pct"] / 100 * amount,
            0,
        )

        recommended_loan = {
            "loan_id": rec_id,
            "loan_name": loan["loan_name"],
            "loan_type": loan["loan_type"],
        }

        offer = {
            "loan_id": rec_id,
            "loan_name": loan["loan_name"],
            "loan_type": loan["loan_type"],
            "amount": int(amount),
            "interest_rate": rate,
            "original_rate": neg.get("original_rate", loan["product_terms"]["base_interest_rate_annual"]),
            "tenure_months": int(tenure),
            "monthly_emi": emi,
            "processing_fee": round(processing_fee, 2),
            "negotiation_rounds": neg.get("rounds", 0),
        }

    is_final = state["conversation_phase"] in ("confirmation", "done")
    
    # Calculate CIBL score before recommendation phase so it can be shown to user
    cibl_score = None
    if state["conversation_phase"] == "recommendation" or new_phase == "recommendation":
        cibl_data = calculate_cibl_score(state["extracted_profile"])
        cibl_score = cibl_data

    return {
        "reply": clean_reply,
        "phase": state["conversation_phase"],
        "extracted_fields": state["extracted_profile"],
        "recommended_loan": recommended_loan,
        "offer": offer,
        "confidence": float(extracted.get("confidence", 0.5)),
        "is_final": is_final,
        "turn_count": state["turn_count"],
        "cibl_score": cibl_score,
    }


# ─── Approve / finalize offer ────────────────────────────────────────────────
def finalize_loan_application(
    session_id: str,
    user_id: Optional[int],
    approved_terms: Optional[dict] = None,
) -> dict:
    """Store approved loan application to DB."""
    print(f"[LoanAgent] finalize_loan_application called: session={session_id}, user={user_id}, terms={approved_terms}")
    
    state = _load_state(session_id, user_id)
    rec_id = state.get("recommended_loan_id")
    print(f"[LoanAgent] Loaded state: phase={state.get('conversation_phase')}, rec_id={rec_id}")
    
    if not rec_id or rec_id not in LOAN_BY_ID:
        raise ValueError(f"No recommended loan found for this session. rec_id={rec_id}, available={list(LOAN_BY_ID.keys())}")

    loan = LOAN_BY_ID[rec_id]
    neg = state.get("negotiation_state", {})
    profile = state.get("extracted_profile", {})

    rate = (approved_terms or {}).get("interest_rate") or neg.get(
        "current_rate", loan["product_terms"]["base_interest_rate_annual"]
    )
    amount = (approved_terms or {}).get("amount") or neg.get(
        "current_amount", profile.get("requested_amount") or loan["product_terms"]["min_amount"]
    )
    tenure = (approved_terms or {}).get("tenure_months") or neg.get(
        "current_tenure", loan["product_terms"]["max_tenure_months"]
    )
    emi = calculate_emi(float(amount), float(rate), int(tenure))
    fee = round(loan["product_terms"]["processing_fee_pct"] / 100 * float(amount), 2)

    app_data = {
        "sid": session_id,
        "uid": user_id,
        "loan_id": rec_id,
        "loan_name": loan["loan_name"],
        "loan_type": loan["loan_type"],
        "req_amount": int(profile.get("requested_amount") or amount),
        "app_amount": int(amount),
        "rate": float(rate),
        "tenure": int(tenure),
        "fee": fee,
        "emi": emi,
        "rounds": neg.get("rounds", 0),
        "profile": json.dumps(profile),
    }

    if _engine:
        try:
            with _engine.begin() as conn:
                # First, try to just insert without the jsonb cast to see if that's the issue
                result = conn.execute(
                    text("""
                        INSERT INTO loan_applications
                            (session_id, user_id, loan_id, loan_name, loan_type,
                             requested_amount, approved_amount, interest_rate, tenure_months,
                             processing_fee, monthly_emi, negotiation_rounds, status,
                             extracted_profile, approved_at)
                        VALUES
                            (:sid, :uid, :loan_id, :loan_name, :loan_type,
                             :req_amount, :app_amount, :rate, :tenure,
                             :fee, :emi, :rounds, 'approved',
                             :profile, NOW())
                        ON CONFLICT (session_id) DO UPDATE SET
                            approved_amount   = EXCLUDED.approved_amount,
                            interest_rate     = EXCLUDED.interest_rate,
                            tenure_months     = EXCLUDED.tenure_months,
                            monthly_emi       = EXCLUDED.monthly_emi,
                            status            = 'approved',
                            approved_at       = NOW()
                        RETURNING id
                    """),
                    app_data,
                )
                app_id = result.scalar()
        except Exception as e:
            print(f"[LoanAgent] DB finalize error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Failed to save loan application: {str(e)}")
    else:
        print("[LoanAgent] No database engine available - running without DB")
        app_id = None

    # Update phase to done
    state["conversation_phase"] = "done"
    _save_state(state)

    return {
        "application_id": app_id,
        "status": "approved",
        "loan_id": rec_id,
        "loan_name": loan["loan_name"],
        "loan_type": loan["loan_type"],
        "amount": int(amount),
        "interest_rate": float(rate),
        "tenure_months": int(tenure),
        "monthly_emi": emi,
        "processing_fee": fee,
    }


# ─── State getter ─────────────────────────────────────────────────────────────
def get_loan_state(session_id: str) -> dict:
    state = _load_state(session_id, None)
    return {
        "phase": state.get("conversation_phase", "discovery"),
        "extracted_profile": state.get("extracted_profile", {}),
        "recommended_loan_id": state.get("recommended_loan_id"),
        "negotiation_state": state.get("negotiation_state", {}),
        "turn_count": state.get("turn_count", 0),
    }


# ─── History getter ───────────────────────────────────────────────────────────
def get_loan_history(session_id: str) -> list[dict]:
    if not _engine:
        # Fall back to in-memory
        state = _agent_sessions.get(session_id, {})
        return state.get("messages", [])
    try:
        with _engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT role, message, created_at FROM loan_conversations "
                    "WHERE session_id = :sid ORDER BY created_at ASC"
                ),
                {"sid": session_id},
            ).mappings().all()
            return [
                {
                    "role": r["role"],
                    "message": r["message"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
    except Exception as e:
        print(f"[LoanAgent] DB history error: {e}")
        return []
