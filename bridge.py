def phase1_to_offer_request(phase1_output: dict) -> dict:
    """
    Converts Phase1Output dict from workflow1 into the OfferRequest
    format expected by loans8.

    phase1_output structure (from workflow1/schema.py Phase1Output):
      session_id, query, policy_inputs (PolicyInputs fields)

    loans8 OfferRequest structure (from loans8/api/schemas.py):
      session_id, query, loan_choice_index, policy_inputs,
      negotiate, negotiation_inputs
    """
    return {
        "session_id": phase1_output["session_id"],
        "query": phase1_output["query"],
        "loan_choice_index": None,
        "policy_inputs": {
            "age": phase1_output["policy_inputs"]["age"],
            "employment_type": phase1_output["policy_inputs"]["employment_type"],
            "gross_monthly_income": phase1_output["policy_inputs"]["gross_monthly_income"],
            "net_monthly_income": phase1_output["policy_inputs"]["net_monthly_income"],
            "existing_emi_monthly": phase1_output["policy_inputs"]["existing_emi_monthly"],
            "credit_score": phase1_output["policy_inputs"]["credit_score"],
            "fraud_score": phase1_output["policy_inputs"]["fraud_score"],
            "risk_persona": phase1_output["policy_inputs"]["risk_persona"],
            "intent_category": phase1_output["policy_inputs"].get("intent_category"),
            "requested_amount": phase1_output["policy_inputs"]["requested_amount"],
            "preferred_tenure_months": phase1_output["policy_inputs"].get("preferred_tenure_months"),
            "collateral_offered": phase1_output["policy_inputs"].get("collateral_offered", False),
            "collateral_value": phase1_output["policy_inputs"].get("collateral_value"),
            "missed_payments_last_12m": phase1_output["policy_inputs"].get("missed_payments_last_12m", 0),
        },
        "negotiate": False,
        "negotiation_inputs": [],
    }
