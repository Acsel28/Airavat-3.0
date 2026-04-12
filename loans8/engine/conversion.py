from __future__ import annotations

from loans8.api.schemas import NegotiationState


def compute_conversion_probability(state: NegotiationState, latest_intent: str) -> float:
    prob = 0.50

    if latest_intent == "accepting":
        prob += 0.15
    if latest_intent == "rejecting":
        prob -= 0.20

    rejection_count = sum(1 for r in state.round_log if r.user_intent == "rejecting")
    if rejection_count >= 2:
        prob -= 0.20

    if state.rounds_elapsed <= 2:
        prob += 0.10

    if state.rounds_elapsed > 4:
        prob -= 0.10 * (state.rounds_elapsed - 4)

    return max(0.05, min(0.95, prob))


def recommend_concession(
    state: NegotiationState,
    conversion_prob: float,
    latest_intent: str,
) -> str | None:
    if conversion_prob > 0.70:
        return "hold"

    if state.rounds_elapsed >= state.max_rounds:
        return "escalate"

    ct = state.concession_tracker
    hl = state.hard_limits

    intent_lever_map = {
        "wants_more_amount": "amount",
        "wants_lower_emi": "tenure",
        "wants_lower_rate": "rate",
        "wants_longer_tenure": "tenure",
        "wants_fee_waiver": "fee",
    }
    preferred = intent_lever_map.get(latest_intent)

    if preferred == "amount" and ct.amount_extended_pct < hl.get("max_amount_extension_pct", 15.0):
        return "amount"
    if preferred == "tenure" and not ct.tenure_extended:
        return "tenure"
    if preferred == "rate" and ct.rate_discounted_pct < hl.get("max_rate_discount_pct", 0.75):
        return "rate"
    if preferred == "fee" and ct.fee_waived_pct < 100.0:
        return "fee"

    if ct.amount_extended_pct < hl.get("max_amount_extension_pct", 15.0):
        return "amount"
    if not ct.tenure_extended:
        return "tenure"
    if ct.rate_discounted_pct < hl.get("max_rate_discount_pct", 0.75):
        return "rate"
    if ct.fee_waived_pct < 100.0:
        return "fee"

    return "escalate"


def compute_concession_increment(lever: str, state: NegotiationState, conversion_prob: float) -> float:
    ct = state.concession_tracker
    hl = state.hard_limits

    if lever == "amount":
        used = ct.amount_extended_pct
        max_ext = hl.get("max_amount_extension_pct", 15.0)
        if used == 0:
            return min(5.0, max_ext)
        if used <= 5.0:
            return min(5.0, max_ext - used)
        return min(5.0, max_ext - used)

    if lever == "rate":
        used = ct.rate_discounted_pct
        max_disc = hl.get("max_rate_discount_pct", 0.75)
        return min(0.25, max_disc - used)

    if lever == "fee":
        used = ct.fee_waived_pct
        if used == 0:
            return 50.0
        if used < 100.0:
            return 100.0 - used
        return 0.0

    if lever == "tenure":
        return 1

    return 0.0
