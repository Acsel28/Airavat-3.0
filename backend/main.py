"""
AI Video Onboarding System - FastAPI Backend
Handles liveness detection, AI text responses, and session tracking.
"""

import base64
import importlib.metadata
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import sqlite3
import json
import math
import asyncio

# CRITICAL: Load environment variables BEFORE any other imports
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass

import numpy as np
import cv2
import mediapipe as mp
import face_recognition
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from user_me import get_me as get_me_endpoint
from loan_agent import loan_chat, finalize_loan_application, get_loan_state, get_loan_history
from pydantic import BaseModel, Field
from typing import Optional, List
import random

app = FastAPI(title="AI Onboarding Backend", version="1.1.0")

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost",
).split(",")
_cors_origins = [o.strip() for o in _cors_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_api_route(
    "/get_me",
    get_me_endpoint,
    methods=["GET"],
    tags=["auth"],
)

# ─── MediaPipe ───────────────────────────────────────────────────────────────
mp_face_detection = mp.solutions.face_detection
face_detector = mp_face_detection.FaceDetection(
    model_selection=0, min_detection_confidence=0.5
)

# Realtime tuning knobs
FRAME_SCALE = 0.5
AUTHORIZED_COSINE_THRESHOLD = 0.92
EMBEDDING_DB_PATH = "authorized_embeddings.db"
VIOLATION_TIMEOUT_SECONDS = 30
MAX_VIOLATIONS = 100

# ─── In-memory state ─────────────────────────────────────────────────────────
last_frame_time: float = 0.0

# Session store: session_id → {messages, liveness_samples, created_at}
sessions: dict = {}


def init_embedding_db():
    conn = sqlite3.connect(EMBEDDING_DB_PATH)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS authorized_embeddings (
                session_id TEXT PRIMARY KEY,
                embedding_json TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_authorized_embedding(session_id: str, embedding: np.ndarray):
    conn = sqlite3.connect(EMBEDDING_DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO authorized_embeddings(session_id, embedding_json, created_at)
            VALUES(?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                embedding_json=excluded.embedding_json,
                created_at=excluded.created_at
            """,
            (session_id, json.dumps(embedding.tolist()), time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def load_authorized_embedding(session_id: str) -> Optional[np.ndarray]:
    conn = sqlite3.connect(EMBEDDING_DB_PATH)
    try:
        row = conn.execute(
            "SELECT embedding_json FROM authorized_embeddings WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return np.array(json.loads(row[0]), dtype=np.float32)


def delete_authorized_embedding(session_id: str):
    conn = sqlite3.connect(EMBEDDING_DB_PATH)
    try:
        conn.execute("DELETE FROM authorized_embeddings WHERE session_id = ?", (session_id,))
        conn.commit()
    finally:
        conn.close()


init_embedding_db()


# ─── Models ──────────────────────────────────────────────────────────────────
class FrameRequest(BaseModel):
    image: str          # base64 JPEG/PNG
    session_id: Optional[str] = "default"


class BoundingBox(BaseModel):
    x: float; y: float; w: float; h: float   # normalised 0–1


class FrameResponse(BaseModel):
    liveness_score: float
    face_detected: bool
    face_count: int
    movement_detected: bool
    frame_diff_score: float
    is_verified: bool
    security_alert: Optional[str] = None
    violation_active: bool
    timer_running: bool
    violation_count: int
    violation_seconds_remaining: int
    meeting_terminated: bool
    meeting_end_message: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    debug: dict


class AgeFrameRequest(BaseModel):
    frames: List[str] = Field(default_factory=list)  # base64 JPEG frames
    image: Optional[str] = None


class AgePredictionResponse(BaseModel):
    ages: List[float]
    average_age: float
    frames_processed: int
    confidence: float


class TextRequest(BaseModel):
    text: str
    session_id: Optional[str] = "default"


class SpeechRequest(BaseModel):
    text: str
    voice: str = "marin"
    instructions: Optional[str] = "Speak in a warm, natural, human-like onboarding assistant voice."
    response_format: str = "wav"


class AvatarTalkRequest(BaseModel):
    text: str


class STTRequest(BaseModel):
    audio: str  # data URL or raw base64 audio payload
    language: Optional[str] = "en"


class STTResponse(BaseModel):
    text: str
    provider: str


class TextResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    session_id: str
    provider: str
    suggestions: Optional[List[str]] = None


class SessionResponse(BaseModel):
    session_id: str
    message_count: int
    avg_liveness: float
    duration_seconds: float
    intents: List[str]
    has_face_embedding: bool
    security_blocked: bool
    security_alert_reason: Optional[str] = None
    violation_count: int
    meeting_terminated: bool


# ─── Onboarding dialogue ─────────────────────────────────────────────────────
ONBOARDING_RESPONSES = {
    "greeting": [
        "Welcome! I'm your AI onboarding assistant. Let's get you set up — could you start by telling me your name?",
        "Hello there! Great to meet you. I'm here to guide you through onboarding. What's your name?",
    ],
    "name": [
        "Lovely to meet you! What role will you be joining us in?",
        "Great name! And what position are you starting in?",
    ],
    "role": [
        "Excellent! Our platform makes team collaboration seamless. Have you used similar tools before?",
        "Perfect. You'll fit right in. Are you familiar with project management platforms?",
    ],
    "experience": [
        "That's helpful context. The three key areas are your dashboard, task boards, and real-time collaboration tools. Any questions so far?",
        "Great background! You'll pick this up quickly. Main areas: dashboard, team spaces, and analytics. What would you like to explore first?",
    ],
    "question": [
        "Great question! All settings are accessible from the top-right menu. Anything else on your mind?",
        "Absolutely! Click the help icon anytime for guided tutorials. Need anything else?",
    ],
    "default": [
        "I understand. Is there anything specific about the onboarding process you'd like to know more about?",
        "Thanks for sharing that. We're making great progress. How are you feeling about everything so far?",
        "Got it! You're doing great. Just a few more steps and you'll be all set.",
    ],
    "done": [
        "You're all set! Welcome aboard — your account is fully configured. Feel free to explore!",
        "Onboarding complete! You're officially part of the team. Reach out if you ever need help.",
    ],
}


def classify_intent(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["hello", "hi", "hey", "start", "begin"]):      return "greeting"
    if any(w in t for w in ["my name is", "i'm", "i am", "call me"]):      return "name"
    if any(w in t for w in ["engineer", "developer", "designer", "manager",
                              "analyst", "lead", "role", "position"]):       return "role"
    if any(w in t for w in ["yes", "no", "used", "experience", "familiar",
                              "worked", "tried", "before"]):                  return "experience"
    if any(w in t for w in ["how", "what", "where", "when", "why", "?",
                              "question", "help"]):                           return "question"
    if any(w in t for w in ["done", "finish", "complete", "goodbye", "bye"]):return "done"
    return "default"


# ─── Liveness helpers ─────────────────────────────────────────────────────────
def decode_image(b64: str) -> np.ndarray:
    if "," in b64:
        b64 = b64.split(",")[1]
    arr = np.frombuffer(base64.b64decode(b64), dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img


def predict_age_from_image(img_bgr: np.ndarray) -> float:
    # Import DeepFace lazily so backend can boot even if TF init is slow/problematic.
    import tensorflow as tf

    if not hasattr(tf, "__version__"):
        try:
            tf.__version__ = importlib.metadata.version("tensorflow")
        except Exception:
            tf.__version__ = "2.0.0"

    # Keep DeepFace cache/model files inside the project to avoid profile permission issues.
    deepface_home = os.path.join(os.path.dirname(__file__), ".deepface")
    os.makedirs(deepface_home, exist_ok=True)
    os.environ["DEEPFACE_HOME"] = deepface_home

    from deepface import DeepFace

    result = DeepFace.analyze(
        img_path=img_bgr,
        actions=["age"],
        enforce_detection=False,
        silent=True,
    )

    # DeepFace may return a dict or a list containing a dict depending on version.
    if isinstance(result, list):
        return float(result[0]["age"])
    return float(result["age"])


def detect_faces(img_rgb: np.ndarray):
    """Return all detected face boxes as normalised dicts (0-1)."""
    results = face_detector.process(img_rgb)
    if not results.detections:
        return []

    boxes = []
    for det in results.detections:
        bb = det.location_data.relative_bounding_box
        boxes.append({"x": bb.xmin, "y": bb.ymin, "w": bb.width, "h": bb.height})
    return boxes


def detect_face(img_rgb: np.ndarray):
    """Compatibility helper: return (detected, first_bbox)."""
    boxes = detect_faces(img_rgb)
    if not boxes:
        return False, None
    return True, boxes[0]


def crop_face(img_bgr: np.ndarray, bbox: dict, pad_ratio: float = 0.15) -> np.ndarray:
    """Crop face region with a small padding margin."""
    h, w = img_bgr.shape[:2]
    x = int(bbox["x"] * w)
    y = int(bbox["y"] * h)
    bw = int(bbox["w"] * w)
    bh = int(bbox["h"] * h)

    pad_x = int(bw * pad_ratio)
    pad_y = int(bh * pad_ratio)

    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(w, x + bw + pad_x)
    y2 = min(h, y + bh + pad_y)

    if x2 <= x1 or y2 <= y1:
        return img_bgr
    return img_bgr[y1:y2, x1:x2]


def compute_cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)
    if a_norm == 0 or b_norm == 0:
        return 0.0
    return float(np.dot(a, b) / (a_norm * b_norm))


def extract_face_embedding(img_rgb: np.ndarray, bbox: dict) -> Optional[np.ndarray]:
    """Extract robust 128D embedding from a single detected face box."""
    h, w, _ = img_rgb.shape
    left = max(0, int(bbox["x"] * w))
    top = max(0, int(bbox["y"] * h))
    right = min(w, int((bbox["x"] + bbox["w"]) * w))
    bottom = min(h, int((bbox["y"] + bbox["h"]) * h))

    if right <= left or bottom <= top:
        return None

    # face_recognition expects location order: (top, right, bottom, left).
    encodings = face_recognition.face_encodings(
        img_rgb,
        known_face_locations=[(top, right, bottom, left)],
        num_jitters=1,
        model="small",
    )
    if not encodings:
        return None
    return np.array(encodings[0], dtype=np.float32)


def compute_frame_diff(cur: np.ndarray, prev: np.ndarray) -> float:
    if prev.shape != cur.shape:
        prev = cv2.resize(prev, (cur.shape[1], cur.shape[0]))
    diff = cv2.absdiff(cur, prev)
    return min(float(np.mean(diff)) / 255.0 * 10, 1.0)


def compute_liveness(face: bool, movement: bool, diff: float) -> float:
    s = 0.0
    if face:     s += 0.4
    if movement: s += 0.3
    s += 0.3 * min(diff, 1.0)
    return round(min(s, 1.0), 3)


def resize_for_realtime(img_bgr: np.ndarray) -> np.ndarray:
    if FRAME_SCALE >= 1.0:
        return img_bgr
    h, w = img_bgr.shape[:2]
    return cv2.resize(
        img_bgr,
        (max(1, int(w * FRAME_SCALE)), max(1, int(h * FRAME_SCALE))),
        interpolation=cv2.INTER_AREA,
    )

def get_or_create_session(session_id: str) -> dict:
    if session_id not in sessions:
        stored_embedding = load_authorized_embedding(session_id)
        sessions[session_id] = {
            "messages": [],
            "liveness_samples": [],
            "intents": [],
            "authorized_embedding": stored_embedding,
            "previous_gray_frame": None,
            "violation_active": False,
            "timer_running": False,
            "violation_count": 0,
            "violation_start_time": None,
            "meeting_terminated": False,
            "meeting_end_message": None,
            "created_at": time.time(),
        }
    return sessions[session_id]


def build_fallback_reply(text: str, intent: str) -> str:
    cleaned = text.strip()
    if cleaned:
        return f"I heard you say: {cleaned}. Tell me a little more so I can help with the next onboarding step."
    replies = ONBOARDING_RESPONSES.get(intent, ONBOARDING_RESPONSES["default"])
    return random.choice(replies)


def generate_ai_reply(text: str) -> tuple[str, str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return build_fallback_reply(text, classify_intent(text)), "fallback"
    try:
        # Lazy import - Gemini client may not be installed in all environments
        from google import genai
    except Exception:
        return build_fallback_reply(text, classify_intent(text)), "fallback"

    try:
        client = genai.Client(api_key=api_key)
        prompt = (
            "You are a warm onboarding assistant. "
            "Reply conversationally in 1 to 3 short sentences, staying helpful and natural. "
            "Avoid generic filler and directly address the specific user message. "
            "User message: "
            f"{text}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        reply = getattr(response, "text", "") or ""
        if not reply.strip():
            raise HTTPException(status_code=502, detail="Gemini returned an empty reply")
        return reply.strip(), "gemini"
    except Exception:
        return build_fallback_reply(text, classify_intent(text)), "fallback"


def generate_speech_audio(text: str, voice: str, instructions: Optional[str], response_format: str) -> bytes:
    provider = os.getenv("TTS_PROVIDER", "local").strip().lower()

    if provider == "local":
        try:
            from TTS.api import TTS  # type: ignore
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="Local TTS is unavailable. Install `TTS` or set TTS_PROVIDER=elevenlabs.",
            ) from exc

        model_name = os.getenv("COQUI_TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC")
        try:
            model = TTS(model_name=model_name, progress_bar=False, gpu=False)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                temp_path = tmp.name
            try:
                model.tts_to_file(text=text, file_path=temp_path)
                with open(temp_path, "rb") as f:
                    return f.read()
            finally:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Local TTS generation failed: {exc}") from exc

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY is not configured on the backend")

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
    model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    output_format = "mp3_44100_128"
    if response_format == "wav":
        output_format = "pcm_44100"

    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.15,
            "use_speaker_boost": True,
        },
    }

    request = urllib.request.Request(
        url=f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={output_format}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg" if output_format.startswith("mp3") else "audio/wav",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=exc.code, detail=f"ElevenLabs TTS request failed: {detail}")
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"ElevenLabs TTS request failed: {exc.reason}")


def transcribe_audio_with_local_model(audio_b64: str, language: Optional[str]) -> str:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Local STT is unavailable. Install `faster-whisper` or set STT_PROVIDER=deepgram.",
        ) from exc

    if "," in audio_b64:
        header, payload = audio_b64.split(",", 1)
    else:
        header, payload = "", audio_b64

    try:
        audio_bytes = base64.b64decode(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio payload: {exc}") from exc

    suffix = ".webm"
    if "audio/wav" in header or "audio/x-wav" in header:
        suffix = ".wav"
    elif "audio/mp3" in header or "audio/mpeg" in header:
        suffix = ".mp3"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        temp_path = tmp.name
        tmp.write(audio_bytes)

    model_size = os.getenv("WHISPER_MODEL_SIZE", "tiny")
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    try:
        model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
        segments, _ = model.transcribe(temp_path, language=(language or None), vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments if getattr(seg, "text", "").strip()).strip()
        if not text:
            raise HTTPException(status_code=422, detail="No speech recognized in audio")
        return text
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Local STT failed: {exc}") from exc
    finally:
        try:
            os.remove(temp_path)
        except Exception:
            pass


def transcribe_audio_with_deepgram(audio_b64: str, language: Optional[str]) -> str:
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="DEEPGRAM_API_KEY is not configured on the backend")

    if "," in audio_b64:
        header, payload = audio_b64.split(",", 1)
    else:
        header, payload = "", audio_b64

    try:
        audio_bytes = base64.b64decode(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio payload: {exc}") from exc

    content_type = "audio/webm"
    if "audio/wav" in header or "audio/x-wav" in header:
        content_type = "audio/wav"
    elif "audio/mp3" in header or "audio/mpeg" in header:
        content_type = "audio/mpeg"

    query_lang = f"&language={language}" if language else ""
    request = urllib.request.Request(
        url=f"https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true{query_lang}",
        data=audio_bytes,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": content_type,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(raw)
            text = (
                data.get("results", {})
                .get("channels", [{}])[0]
                .get("alternatives", [{}])[0]
                .get("transcript", "")
                .strip()
            )
            if not text:
                raise HTTPException(status_code=422, detail="No speech recognized in audio")
            return text
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=exc.code, detail=f"Deepgram STT request failed: {detail}")
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Deepgram STT request failed: {exc.reason}")


def did_request(path: str, method: str = "GET", payload: Optional[dict] = None) -> dict:
    api_key = os.getenv("DID_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="DID_API_KEY is not configured on the backend")

    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=f"https://api.d-id.com{path}",
        data=body,
        headers={
            "Authorization": f"Basic {api_key}",
            "Content-Type": "application/json",
        },
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(status_code=exc.code, detail=f"D-ID request failed: {detail}")
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"D-ID request failed: {exc.reason}")


def create_did_talk(text: str) -> dict:
    source_url = os.getenv("DID_SOURCE_URL")
    if not source_url:
        raise HTTPException(status_code=503, detail="DID_SOURCE_URL is not configured on the backend")

    payload = {
        "source_url": source_url,
        "script": {
            "type": "text",
            "subtitles": "false",
            "provider": {
                "type": "microsoft",
                "voice_id": os.getenv("DID_VOICE_ID", "en-US-JennyNeural"),
            },
            "input": text,
        },
        "config": {
            "fluent": True,
            "pad_audio": 0.0,
        },
    }

    talk = did_request("/talks", method="POST", payload=payload)
    talk_id = talk.get("id")
    if not talk_id:
        raise HTTPException(status_code=502, detail="D-ID did not return a talk id")

    for _ in range(40):
        status = did_request(f"/talks/{talk_id}")
        if status.get("status") == "done":
            return status
        if status.get("status") in {"error", "rejected"}:
            raise HTTPException(status_code=502, detail=f"D-ID talk failed: {status}")
        time.sleep(2)

    raise HTTPException(status_code=504, detail="D-ID talk generation timed out")


# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/analyze-frame", response_model=FrameResponse)
async def analyze_frame(req: FrameRequest):
    global last_frame_time

    try:
        img_bgr = decode_image(req.image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    # Resize once for all realtime operations (face + movement + embedding).
    img_bgr_small = resize_for_realtime(img_bgr)
    img_rgb  = cv2.cvtColor(img_bgr_small, cv2.COLOR_BGR2RGB)
    img_gray = cv2.cvtColor(img_bgr_small, cv2.COLOR_BGR2GRAY)

    boxes = detect_faces(img_rgb)
    face_count = len(boxes)
    face_detected = face_count > 0
    bbox = boxes[0] if boxes else None

    sess = get_or_create_session(req.session_id or "default")

    frame_diff_score = 0.0
    movement_detected = False
    if sess["previous_gray_frame"] is not None:
        frame_diff_score  = compute_frame_diff(img_gray, sess["previous_gray_frame"])
        movement_detected = frame_diff_score > 0.01

    sess["previous_gray_frame"] = img_gray.copy()
    last_frame_time = time.time()

    security_alert = None
    is_verified = False
    similarity = None
    meeting_end_message = None

    if sess["meeting_terminated"]:
        return FrameResponse(
            liveness_score=compute_liveness(face_detected, movement_detected, frame_diff_score),
            face_detected=face_detected,
            face_count=face_count,
            movement_detected=movement_detected,
            frame_diff_score=round(frame_diff_score, 4),
            is_verified=False,
            security_alert="meeting_ended",
            violation_active=False,
            timer_running=False,
            violation_count=sess["violation_count"],
            violation_seconds_remaining=0,
            meeting_terminated=True,
            meeting_end_message=sess["meeting_end_message"] or "Meeting ended due to multiple identity violations.",
            bounding_box=BoundingBox(**bbox) if bbox else None,
            debug={
                "img_shape": list(img_bgr_small.shape),
                "timestamp": last_frame_time,
                "cosine_similarity": None,
                "has_reference_embedding": sess["authorized_embedding"] is not None,
                "security_blocked": True,
                "security_alert_reason": "meeting_ended",
                "cosine_threshold": AUTHORIZED_COSINE_THRESHOLD,
                "frame_scale": FRAME_SCALE,
            },
        )

    # Strict identity lock: compare only with the original session-authorized embedding.
    if face_count == 0:
        security_alert = "no_face"
    elif face_count > 1:
        security_alert = "multiple_faces"
    elif face_count == 1:
        current_embedding = extract_face_embedding(img_rgb, boxes[0])
        if current_embedding is None:
            security_alert = "embedding_failed"
        elif sess["authorized_embedding"] is None:
            # Enrollment step: first valid single face becomes authorized identity.
            sess["authorized_embedding"] = current_embedding
            save_authorized_embedding(req.session_id or "default", current_embedding)
            is_verified = True
        else:
            similarity = compute_cosine_similarity(sess["authorized_embedding"], current_embedding)
            if similarity >= AUTHORIZED_COSINE_THRESHOLD:
                is_verified = True
            else:
                security_alert = "different_person"

    valid_face = is_verified and security_alert is None
    now_ts = time.time()

    if valid_face:
        # Original authorized face returned: clear violation + stop grace timer.
        sess["violation_active"] = False
        sess["timer_running"] = False
        sess["violation_start_time"] = None
    else:
        # Count violation immediately only once per violation event.
        if not sess["violation_active"]:
            sess["violation_count"] += 1
            sess["violation_active"] = True
            sess["timer_running"] = True
            sess["violation_start_time"] = now_ts

            if sess["violation_count"] >= MAX_VIOLATIONS:
                sess["meeting_terminated"] = True
                sess["meeting_end_message"] = "Meeting ended due to multiple identity violations."
                sess["timer_running"] = False
                sess["violation_active"] = False
                sess["violation_start_time"] = None
                security_alert = "meeting_ended"
                meeting_end_message = sess["meeting_end_message"]
                is_verified = False
        elif sess["timer_running"] and sess["violation_start_time"] is not None:
            elapsed = now_ts - float(sess["violation_start_time"])
            if elapsed >= VIOLATION_TIMEOUT_SECONDS:
                # Grace period expired while still invalid -> terminate immediately.
                sess["meeting_terminated"] = True
                sess["meeting_end_message"] = "Meeting ended due to multiple identity violations."
                sess["timer_running"] = False
                sess["violation_active"] = False
                sess["violation_start_time"] = None
                security_alert = "meeting_ended"
                meeting_end_message = sess["meeting_end_message"]
                is_verified = False

    if security_alert:
        is_verified = False

    remaining_seconds = 0
    if sess["timer_running"] and sess["violation_start_time"] is not None:
        elapsed = now_ts - float(sess["violation_start_time"])
        remaining_seconds = max(0, int(math.ceil(VIOLATION_TIMEOUT_SECONDS - elapsed)))

    liveness = compute_liveness(face_detected, movement_detected, frame_diff_score)

    # Record liveness in session
    sess["liveness_samples"].append(liveness)
    # Keep only last 100 samples
    if len(sess["liveness_samples"]) > 100:
        sess["liveness_samples"] = sess["liveness_samples"][-100:]

    return FrameResponse(
        liveness_score=liveness,
        face_detected=face_detected,
        face_count=face_count,
        movement_detected=movement_detected,
        frame_diff_score=round(frame_diff_score, 4),
        is_verified=is_verified,
        security_alert=security_alert,
        violation_active=sess["violation_active"],
        timer_running=sess["timer_running"],
        violation_count=sess["violation_count"],
        violation_seconds_remaining=remaining_seconds,
        meeting_terminated=sess["meeting_terminated"],
        meeting_end_message=meeting_end_message or sess["meeting_end_message"],
        bounding_box=BoundingBox(**bbox) if bbox else None,
        debug={
            "img_shape": list(img_bgr_small.shape),
            "timestamp": last_frame_time,
            "cosine_similarity": round(similarity, 4) if similarity is not None else None,
            "has_reference_embedding": sess["authorized_embedding"] is not None,
            "security_blocked": sess["meeting_terminated"],
            "security_alert_reason": security_alert,
            "cosine_threshold": AUTHORIZED_COSINE_THRESHOLD,
            "frame_scale": FRAME_SCALE,
            "violation_timeout_seconds": VIOLATION_TIMEOUT_SECONDS,
            "max_violations": MAX_VIOLATIONS,
        },
    )


@app.post("/process-text", response_model=TextResponse)
async def process_text(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    intent  = classify_intent(req.text)
    reply, provider = generate_ai_reply(req.text)

    sess_id = req.session_id or str(uuid.uuid4())
    sess    = get_or_create_session(sess_id)
    sess["messages"].append({"role": "user",      "text": req.text, "ts": time.time()})
    sess["messages"].append({"role": "assistant",  "text": reply,    "ts": time.time()})
    sess["intents"].append(intent)

    # Provide optional follow-up suggestions when intent is vague/default.
    suggestions = None
    if intent == "default":
        suggestions = [
            "Can you tell me your role and experience?",
            "What would you like to learn about the platform?",
            "Do you have any questions about onboarding steps?",
        ]

    return TextResponse(
        reply=reply,
        intent=intent,
        confidence=round(random.uniform(0.82, 0.99), 2),
        session_id=sess_id,
        provider=provider,
        suggestions=suggestions,
    )


@app.post("/api/avatar/talk")
async def avatar_talk(req: AvatarTalkRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    talk = create_did_talk(text)
    result_url = talk.get("result_url") or talk.get("audio_url")
    if not result_url:
        raise HTTPException(status_code=502, detail=f"D-ID did not return a playable result: {talk}")

    return {
        "id": talk.get("id"),
        "status": talk.get("status"),
        "result_url": result_url,
    }


@app.post("/api/speak")
async def speak_text(req: SpeechRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    audio_bytes = generate_speech_audio(
        text=text,
        voice=req.voice,
        instructions=req.instructions,
        response_format=req.response_format,
    )

    media_type = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "opus": "audio/ogg",
        "aac": "audio/aac",
        "flac": "audio/flac",
        "pcm": "application/octet-stream",
    }.get(req.response_format, "audio/wav")

    return Response(content=audio_bytes, media_type=media_type)


@app.post("/api/stt", response_model=STTResponse)
async def speech_to_text(req: STTRequest):
    if not req.audio.strip():
        raise HTTPException(status_code=400, detail="Audio payload cannot be empty")

    provider = os.getenv("STT_PROVIDER", "local").strip().lower()
    if provider == "local":
        text = transcribe_audio_with_local_model(req.audio, req.language)
        return STTResponse(text=text, provider="faster-whisper")

    text = transcribe_audio_with_deepgram(req.audio, req.language)
    return STTResponse(text=text, provider="deepgram")


@app.post("/predict-age", response_model=AgePredictionResponse)
async def predict_age(req: AgeFrameRequest):
    frames = list(req.frames)
    if req.image:
        frames.append(req.image)

    if not frames:
        raise HTTPException(status_code=400, detail="No frames provided")

    ages: List[float] = []
    errors: List[str] = []
    for frame_b64 in frames:
        try:
            img_bgr = decode_image(frame_b64)
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            face_detected, bbox = detect_face(img_rgb)
            if not face_detected:
                errors.append("MediaPipe could not find a face in one frame")
                continue

            age = predict_age_from_image(crop_face(img_bgr, bbox))
            ages.append(age)
        except Exception as exc:
            # Keep processing other frames, but preserve the real error.
            errors.append(str(exc))
            continue

    if not ages:
        detail = "No usable face frames were found"
        if errors:
            detail = f"{detail}. Last error: {errors[-1]}"
        raise HTTPException(status_code=422, detail=detail)

    avg_age = float(sum(ages) / len(ages))
    confidence = max(0.0, 100.0 - (float(np.std(ages)) * 10.0))

    return AgePredictionResponse(
        ages=[round(a, 2) for a in ages],
        average_age=round(avg_age, 2),
        frames_processed=len(ages),
        confidence=round(confidence, 2),
    )


@app.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Return aggregated session analytics."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sess     = sessions[session_id]
    samples  = sess["liveness_samples"]
    avg_live = round(sum(samples) / len(samples), 3) if samples else 0.0
    return SessionResponse(
        session_id=session_id,
        message_count=len(sess["messages"]),
        avg_liveness=avg_live,
        duration_seconds=round(time.time() - sess["created_at"], 1),
        intents=sess["intents"],
        has_face_embedding=sess["authorized_embedding"] is not None,
        security_blocked=sess["meeting_terminated"],
        security_alert_reason=sess["meeting_end_message"],
        violation_count=sess["violation_count"],
        meeting_terminated=sess["meeting_terminated"],
    )


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    sessions.pop(session_id, None)
    delete_authorized_embedding(session_id)
    return {"deleted": session_id}


# ─── Loan Agent Endpoints ──────────────────────────────────────────────────────
class LoanChatRequest(BaseModel):
    session_id: str
    message: str
    user_id: Optional[int] = None
    kyc_profile: Optional[dict] = None


class LoanApproveRequest(BaseModel):
    session_id: str
    user_id: Optional[int] = None
    approved_terms: Optional[dict] = None  # {amount, interest_rate, tenure_months}


@app.post("/loan/chat")
async def loan_chat_endpoint(req: LoanChatRequest):
    """Multi-turn loan advisor conversation."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        result = loan_chat(
            session_id=req.session_id,
            user_message=req.message,
            kyc_profile=req.kyc_profile,
            user_id=req.user_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loan agent error: {e}")


@app.post("/loan/chat-stream")
async def loan_chat_stream_endpoint(req: LoanChatRequest):
    """Streaming version of loan chat - streams response word by word."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    async def event_generator():
        try:
            result = loan_chat(
                session_id=req.session_id,
                user_message=req.message,
                kyc_profile=req.kyc_profile,
                user_id=req.user_id,
            )
            
            # Stream the reply text word by word with small delays for natural feel
            reply_text = result.get("reply", "")
            words = reply_text.split(" ")
            
            for i, word in enumerate(words):
                # Add space after each word except the last
                text_chunk = word + (" " if i < len(words) - 1 else "")
                
                # Send as JSON event
                event_data = {
                    "type": "text",
                    "chunk": text_chunk,
                    "is_final": i == len(words) - 1
                }
                yield f"data: {json.dumps(event_data)}\n\n"
                
                # Small delay for streaming effect
                await asyncio.sleep(0.05)
            
            # Send metadata after text is done
            metadata = {
                "type": "metadata",
                "phase": result.get("phase"),
                "extracted_fields": result.get("extracted_fields"),
                "recommended_loan": result.get("recommended_loan"),
                "offer": result.get("offer"),
                "confidence": result.get("confidence"),
                "is_final": result.get("is_final"),
                "turn_count": result.get("turn_count"),
            }
            yield f"data: {json.dumps(metadata)}\n\n"
            
            # Send completion signal
            yield "data: {\"type\": \"done\"}\n\n"
            
        except Exception as e:
            error_event = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/loan/approve")
async def loan_approve_endpoint(req: LoanApproveRequest):
    """Finalize and approve the loan off
    er."""
    print(f"[LoanApprove] Request received: session={req.session_id}, user={req.user_id}")
    try:
        result = finalize_loan_application(
            session_id=req.session_id,
            user_id=req.user_id,
            approved_terms=req.approved_terms,
        )
        print(f"[LoanApprove] Success: app_id={result.get('application_id')}")
        return result
    except ValueError as e:
        print(f"[LoanApprove] ValueError: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        print(f"[LoanApprove] RuntimeError: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"[LoanApprove] Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@app.get("/loan/state/{session_id}")
async def loan_state_endpoint(session_id: str):
    """Get current loan agent state for a session."""
    return get_loan_state(session_id)


@app.get("/loan/history/{session_id}")
async def loan_history_endpoint(session_id: str):
    """Get full loan conversation history for a session."""
    messages = get_loan_history(session_id)
    return {"session_id": session_id, "messages": messages, "count": len(messages)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AI Onboarding Backend", "version": "1.2.0"}
