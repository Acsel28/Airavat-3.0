1. User Query -> Retrieval

In main.py, user enters free text (Describe what you need a loan for).

get_loan_recommendations() in agent/retrieval.py runs:
classify_intent(query) first.
If any parent type has >=2 keyword hits, it uses keyword_shortcut (direct DB filter by parent type).
Else it uses hybrid_rag.


2. Hybrid RAG scoring

Semantic part:
Query is embedded via Gemini embedding API in engine/gemini_embeddings.py.
Chroma query is run with query_embeddings=[...].
Score conversion: semantic_score = 1 - distance.

Keyword part:
Tokens: words with length >3.
For each loan: keyword_score = hits / len(tokens) where hits is token matches inside description+tags.

Merge:
final_score = semantic_score + 0.3 * keyword_score
match_source: semantic / keyword / both
Top-K sorted descending.


3. Offer generation (deterministic, no LLM)
Implemented in engine/offer_generator.py.

Eligibility gates:
credit_score >= min_credit_score
fraud_score <= 40

Tenure selection:
Use requested tenure if in allowed options, else nearest option.

Amount calculation:
income_eligible_amount = (declared_income_monthly - existing_emi_monthly) * max_foir * tenure_months

If collateral required:
eligible_amount = min(requested_amount, income_eligible_amount, collateral_value * ltv_cap, max_amount)

Else:
eligible_amount = min(requested_amount, income_eligible_amount, max_amount)

Then apply floor:
eligible_amount = max(eligible_amount, min_amount)

Rate calculation:
Start from base_rate, then credit-tier adjustments:
>=800: +0
750-799: +0.25
700-749: +0.75
<700: +1.50
Persona add-ons:
distressed +0.50
first-time +0.25

Clamp: rate = min(rate, max_rate)

EMI:
monthly_rate = rate / 100 / 12
emi = P*r*(1+r)^n / ((1+r)^n - 1) (rounded integer)

FOIR check:
foir = (existing_emi_monthly + emi) / declared_income_monthly
If FOIR too high, binary search amount (max 20 iterations) and recompute EMI.

Fee:
processing_fee = max(eligible_amount * processing_fee_pct / 100, processing_fee_floor_inr)

Negotiation envelope output:
max_amount_allowed = eligible_amount * (1 + amount_delta_pct)
min_rate_allowed = rate - (rate_reduction_bps_max/100) only if conditions pass
tenure options and non-negotiables attached.


4. Negotiation rules + enforcement
Yes, this is LangGraph.

In agent/negotiation_agent.py:

Graph nodes:
present_offer -> get_customer_input -> negotiation_llm -> conditional finalize/loop

Rules source:
Dataset policy in data/loans.py
Offer envelope/non-negotiables from offer generator
LLM system constraints in prompt

Hard enforcement:
_validate_and_clip_terms() clips amount/rate/tenure to envelope bounds.
EMI is always recomputed in Python (LLM EMI is never trusted).

Counter vs deny:
If LLM action is counter, updated terms continue.
If reject_request, it denies that request and loops.
If user says acceptance phrase (okay i accept, etc.), it accepts without extra LLM call.
If stop phrase or call budget reached, escalates.
All transitions are audited via engine/audit.py.



