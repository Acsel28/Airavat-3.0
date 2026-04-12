"""Centralized prompt and UX text constants for the Tier 8 module."""

# =========================
# CLI / MAIN PROMPTS
# =========================

APP_HEADER = "=== TIER 8 — LOAN OFFER & NEGOTIATION AGENT ===\n"
PROMPT_QUERY = "Describe what you need a loan for: "
PROMPT_SELECT_LOAN = "\nSelect loan number to proceed (1-{max_options}): "
PROMPT_NEGOTIATE = "\nWould you like to negotiate the offer? (yes/no): "
PROMPT_NEGOTIATION_INPUT = "Your response: "
NEGOTIATION_PROMPT_INPUT = PROMPT_NEGOTIATION_INPUT

SECTION_POLICY_INPUTS = "\n--- Policy Inputs (simulating bureau + speech extraction) ---"
SECTION_OFFER_GENERATED = "\n=== OFFER GENERATED ==="
SECTION_NEGOTIATION_ENTRY = "\n--- Entering Negotiation Agent ---"
SECTION_AUDIT_TRAIL = "\n--- AUDIT TRAIL ---"

POLICY_PROMPT_INCOME = "Monthly income (INR): "
POLICY_PROMPT_CREDIT_SCORE = "Credit score (300–900): "
POLICY_PROMPT_FRAUD_SCORE = "Fraud score (0–100, lower=safer): "
POLICY_PROMPT_RISK_PERSONA = (
    "Risk persona [standard_borrower/conservative_borrower/distressed_borrower/first_time_borrower]: "
)
POLICY_PROMPT_REQUESTED_AMOUNT = "Requested loan amount (INR): "
POLICY_PROMPT_REQUESTED_TENURE = "Preferred tenure in months (leave blank for auto): "
POLICY_PROMPT_EXISTING_EMI = "Existing monthly EMI obligations (INR): "
POLICY_PROMPT_COLLATERAL = "Collateral value in INR (leave blank if none): "

MSG_INVALID_INTEGER = "Please enter a valid integer."
MSG_INVALID_MIN = "Value must be >= {min_value}."
MSG_INVALID_MAX = "Value must be <= {max_value}."
MSG_INVALID_PERSONA = "Please enter one of the listed risk persona values."
MSG_INVALID_TENURE = "Invalid tenure. Using auto selection."
MSG_INVALID_COLLATERAL = "Invalid collateral value. Treating as none."
MSG_DATA_NOT_READY = "Data store not initialized. Run one-time setup first:"
MSG_DATA_NOT_READY_CMD = "  python main.py --setup"
MSG_NO_QUERY = "No query entered. Exiting."
MSG_NO_RESULTS = "No loan recommendations found. Please try a more specific query."
MSG_TOP_MATCHES = "Top loan matches:"
MSG_INVALID_LOAN_CHOICE = "Please enter a valid option number."
MSG_NOT_ELIGIBLE = "\nNot eligible: {reason}"
MSG_NEGOTIATION_HINT_1 = "You can ask for a higher amount, lower rate, or different tenure."
MSG_NEGOTIATION_HINT_2 = "Type 'accept' to accept the offer or 'stop' to exit negotiation.\n"
MSG_NEGOTIATION_SUMMARY = "\n[Negotiation ended — Status: {status} | Rounds: {rounds}]"
MSG_OFFER_ACCEPTED_AS_IS = "\nOffer accepted as-is. Thank you!"
MSG_NEGOTIATE_YES_NO = "Please enter 'yes' or 'no'."

NEGOTIATION_SYSTEM_PROMPT = """You are Arya, a warm and professional loan advisor at AgentFinance.
You have already collected the customer's full profile. Your job now
is to present loan offers clearly and negotiate fairly if asked.
Rules:
- Keep every response under 3 sentences.
- Never use bullet points or numbered lists when speaking to the user.
- Never ask for information that is already in the customer profile
    (age, income, employment, name — you already have all of this).
- If the customer shares stress or urgency, acknowledge it in one
    brief sentence before moving to the offer.
- Speak amounts in Indian format: ₹5,00,000 not 500000.
- When presenting an offer, always say: amount, then EMI, then tenure.
    Never lead with interest rate.
- When a concession is made, present it as good news, not a negotiation
    concession. Example: "I've managed to get your EMI down to ₹X."""

# =========================
# NEGOTIATION FLOW MESSAGES
# =========================

NEGOTIATION_SECTION_INITIAL = "--- Initial Offer ---"
NEGOTIATION_SECTION_ACCEPTED = "--- Final Status: ACCEPTED ---"
NEGOTIATION_SECTION_ESCALATED = "--- Final Status: ESCALATED ---"

NEGOTIATION_VERBAL_OFFER = (
    "Agent: I can offer {amount} at {rate:.2f}% for {tenure} months. "
    "Your EMI is {emi} per month. How would you like to proceed?"
)
NEGOTIATION_START_MESSAGE = "I can help adjust the terms. What would you like to change?"
NEGOTIATION_EMPTY_INPUT = "Please enter a response (or type 'stop' to exit negotiation)."
NEGOTIATION_ACCEPT_RESPONSE = "Great, thank you for confirming. I will proceed with these terms."
NEGOTIATION_STOP_RESPONSE = "Understood. I will escalate this to a branch officer for offline follow-up."
NEGOTIATION_LLM_LIMIT_RESPONSE = (
    "We have reached the automated negotiation limit for this session. "
    "I will escalate to a branch officer."
)
NEGOTIATION_PARSE_FAIL_RESPONSE = (
    "I want to help further, but I need to escalate this discussion to a branch officer."
)
NEGOTIATION_DEFAULT_VERBAL = "I have updated the offer within policy limits."
NEGOTIATION_UPDATED_OFFER = (
    "Updated Offer: Amount {amount} | Rate {rate:.2f}% | "
    "Tenure {tenure} months | EMI {emi}"
)
NEGOTIATION_ESCALATION_PRINT = "We will connect you with a branch officer to continue this discussion."

# =========================
# NEW NEGOTIATION PROMPTS
# =========================

OFFER_PRESENTATION_PROMPT = """
Customer name: {full_name}
Customer query: {loan_query}
Risk persona: {risk_persona}

Offer details:
- Approved amount: ₹{approved_amount}
- Monthly EMI: ₹{emi_monthly}
- Tenure: {tenure_months} months
- Interest rate: {interest_rate_annual}% per annum
- Processing fee: ₹{processing_fee_amount}

Present this offer warmly in 2-3 sentences. Lead with the amount and EMI.
Mention the tenure briefly. Do not mention interest rate unless the customer
asks. End by asking if they would like to proceed or discuss the terms.
Return plain conversational text only.
"""

NEGOTIATION_TURN_PROMPT = """
Customer's message: {user_utterance}
Current offer: amount ₹{approved_amount}, EMI ₹{emi_monthly},
tenure {tenure_months} months, rate {interest_rate_annual}%
Concession approved by system: {concession_description}
Rounds remaining: {rounds_remaining}
Conversion probability: {conversion_probability}

If concession_description is "hold": restate the value of the offer
warmly without offering anything new. Do not say "I cannot help further."
If concession_description is a real concession: present it as good news
in 1-2 sentences. State the new EMI or amount clearly.
If rounds_remaining <= 1: warmly explain that you have done everything
possible and offer to connect them with a senior advisor.
Return plain conversational text only.

Also return this JSON block at the end, separated by INTENT:
INTENT:
{
    "user_intent": "wants_more_amount|wants_lower_emi|wants_lower_rate|wants_longer_tenure|wants_fee_waiver|accepting|rejecting"
}
"""

ESCALATION_PROMPT = """
You have reached the maximum negotiation rounds.
Customer name: {full_name}

Write one warm sentence telling the customer that a senior loan advisor
will contact them within 24 hours to discuss further options.
Do not say the negotiation failed. Do not apologise excessively.
Return plain text only.
"""

ACCEPTANCE_PROMPT = """
Customer has accepted the loan offer.
Final offer: amount ₹{approved_amount}, EMI ₹{emi_monthly},
tenure {tenure_months} months.

Write 2 sentences:
Sentence 1 — confirm the accepted terms warmly.
Sentence 2 — tell them the next steps (disbursement team will reach out).
Return plain text only.
"""

# =========================
# NEW POLICY INPUT PROMPTS
# =========================

POLICY_PROMPT_AGE = "Age (years): "
POLICY_PROMPT_EMPLOYMENT = "Employment type [salaried/self_employed/business_owner]: "
POLICY_PROMPT_GROSS_INCOME = "Gross monthly income (INR): "
POLICY_PROMPT_NET_INCOME = "Net monthly income (INR): "
