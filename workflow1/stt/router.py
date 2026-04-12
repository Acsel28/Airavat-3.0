from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from stt import storage, transcriber

router = APIRouter()

CONSENT_PHRASES = [
    "i agree",
    "yes i consent",
    "i accept",
    "i confirm",
    "haan",
    "theek hai",
]


@router.post("/stt")
async def stt_endpoint(
    audio: Annotated[UploadFile, File(...)],
    session_id: Annotated[str, Form(...)],
    turn_number: Annotated[int, Form(...)],
    stage: Annotated[str, Form(...)],
) -> dict:
    audio_dir = Path(__file__).resolve().parent / "audio" / session_id
    audio_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    content_type = (audio.content_type or "").lower()
    if "mp4" in content_type:
        ext = "mp4"
    elif "ogg" in content_type:
        ext = "ogg"
    else:
        ext = "webm"
    audio_path = audio_dir / f"turn_{turn_number}_{timestamp}.{ext}"

    with audio_path.open("wb") as buffer:
        while True:
            chunk = await audio.read(1024 * 1024)
            if not chunk:
                break
            buffer.write(chunk)

    if audio_path.stat().st_size == 0:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    result = transcriber.transcribe(str(audio_path))
    transcript = result["transcript"]
    transcript_lower = transcript.lower()
    is_consent = any(phrase in transcript_lower for phrase in CONSENT_PHRASES)

    storage.insert_log(
        session_id=session_id,
        turn_number=turn_number,
        audio_file_path=str(audio_path),
        transcript=transcript,
        confidence=result["confidence"],
        duration_seconds=result["duration_seconds"],
        language=result["language"],
        stage=stage,
        is_consent=is_consent,
    )

    return {
        "session_id": session_id,
        "turn_number": int(turn_number),
        "transcript": transcript,
        "confidence": result["confidence"],
        "duration_seconds": result["duration_seconds"],
        "language": result["language"],
        "audio_file_path": str(audio_path),
        "is_consent": is_consent,
    }
