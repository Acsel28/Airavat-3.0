from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def capture_consent_event(
    session_id: str,
    event_type: str,
    transcript_segment: str,
    offer_snapshot: dict | None = None,
) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    segment_hash = hashlib.sha256(transcript_segment.encode()).hexdigest()

    record = {
        "session_id": session_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "transcript_segment": transcript_segment,
        "transcript_hash": segment_hash,
        "offer_snapshot": offer_snapshot,
    }
    return record
