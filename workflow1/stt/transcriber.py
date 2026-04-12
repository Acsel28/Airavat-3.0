from __future__ import annotations

import math

from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")


def transcribe(audio_path: str) -> dict:
    segments, info = model.transcribe(audio_path, beam_size=5)
    segments = list(segments)

    transcript = " ".join(s.text.strip() for s in segments).strip()

    if segments:
        confidence = sum(math.exp(s.avg_logprob) for s in segments) / len(segments)
        confidence = round(min(1.0, max(0.0, confidence)), 4)
    else:
        confidence = 0.0

    return {
        "transcript": transcript,
        "confidence": confidence,
        "duration_seconds": round(info.duration, 2),
        "language": info.language,
    }
