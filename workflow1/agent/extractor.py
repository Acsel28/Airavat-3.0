from __future__ import annotations

import json

from workflow1.config import REQUIRED_COLLECTED_FIELDS
from workflow1.schema import AgentState, LLMExtractionOutput


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def parse_collection_response(raw: str) -> tuple[str, LLMExtractionOutput | None]:
    if raw.startswith("```"):
        raw = "\n".join(line for line in raw.splitlines() if not line.strip().startswith("```"))
    if "EXTRACTED:" not in raw:
        print("[warn] Missing EXTRACTED block in collection response.")
        return raw.strip(), None
    spoken, extracted_block = raw.split("EXTRACTED:", 1)
    extracted_block = extracted_block.strip()
    try:
        data = json.loads(extracted_block)
    except Exception:
        return spoken.strip(), None

    extracted_fields = data.get("extracted_fields", {})
    confidence_scores = data.get("confidence_scores", {})
    cleaned_confidence: dict[str, float] = {}
    for key, value in confidence_scores.items():
        try:
            cleaned_confidence[key] = _clamp_confidence(value)
        except Exception:
            cleaned_confidence[key] = 0.0

    return (
        spoken.strip(),
        LLMExtractionOutput(
            extracted_fields=extracted_fields,
            confidence_scores=cleaned_confidence,
        ),
    )


def get_missing_required_fields(state: AgentState) -> list[str]:
    return [f for f in REQUIRED_COLLECTED_FIELDS if state.get(f) is None]
