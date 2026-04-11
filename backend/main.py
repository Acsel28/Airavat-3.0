"""
AI Video Onboarding System - FastAPI Backend
Handles liveness detection, AI text responses, and session tracking.
"""

import base64
import importlib.metadata
import os
import time
import uuid
import numpy as np
import cv2
import mediapipe as mp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import random

app = FastAPI(title="AI Onboarding Backend", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── MediaPipe ───────────────────────────────────────────────────────────────
mp_face_detection = mp.solutions.face_detection
face_detector = mp_face_detection.FaceDetection(
    model_selection=0, min_detection_confidence=0.5
)

# ─── In-memory state ─────────────────────────────────────────────────────────
previous_frame: Optional[np.ndarray] = None
last_frame_time: float = 0.0

# Session store: session_id → {messages, liveness_samples, created_at}
sessions: dict = {}


# ─── Models ──────────────────────────────────────────────────────────────────
class FrameRequest(BaseModel):
    image: str          # base64 JPEG/PNG
    session_id: Optional[str] = "default"


class BoundingBox(BaseModel):
    x: float; y: float; w: float; h: float   # normalised 0–1


class FrameResponse(BaseModel):
    liveness_score: float
    face_detected: bool
    movement_detected: bool
    frame_diff_score: float
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


class TextResponse(BaseModel):
    reply: str
    intent: str
    confidence: float
    session_id: str


class SessionResponse(BaseModel):
    session_id: str
    message_count: int
    avg_liveness: float
    duration_seconds: float
    intents: List[str]


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


def detect_face(img_rgb: np.ndarray):
    """Return (detected: bool, bbox: dict|None). bbox values are normalised 0–1."""
    results = face_detector.process(img_rgb)
    if not results.detections:
        return False, None
    det = results.detections[0]
    bb  = det.location_data.relative_bounding_box
    return True, {"x": bb.xmin, "y": bb.ymin, "w": bb.width, "h": bb.height}


def crop_face(img_bgr: np.ndarray, bbox: Optional[dict]) -> np.ndarray:
    if not bbox:
        return img_bgr

    height, width = img_bgr.shape[:2]
    pad_ratio = 0.12

    x1 = max(0, int((bbox["x"] - pad_ratio) * width))
    y1 = max(0, int((bbox["y"] - pad_ratio) * height))
    x2 = min(width, int((bbox["x"] + bbox["w"] + pad_ratio) * width))
    y2 = min(height, int((bbox["y"] + bbox["h"] + pad_ratio) * height))

    if x2 <= x1 or y2 <= y1:
        return img_bgr

    face = img_bgr[y1:y2, x1:x2]
    return face if face.size else img_bgr


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
#mkcdd    

def get_or_create_session(session_id: str) -> dict:
    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "liveness_samples": [],
            "intents": [],
            "created_at": time.time(),
        }
    return sessions[session_id]


# ─── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/analyze-frame", response_model=FrameResponse)
async def analyze_frame(req: FrameRequest):
    global previous_frame, last_frame_time

    try:
        img_bgr = decode_image(req.image)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    img_rgb  = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    face_detected, bbox = detect_face(img_rgb)

    frame_diff_score = 0.0
    movement_detected = False
    if previous_frame is not None:
        frame_diff_score  = compute_frame_diff(img_gray, previous_frame)
        movement_detected = frame_diff_score > 0.01

    previous_frame  = img_gray.copy()
    last_frame_time = time.time()

    liveness = compute_liveness(face_detected, movement_detected, frame_diff_score)

    # Record liveness in session
    sess = get_or_create_session(req.session_id or "default")
    sess["liveness_samples"].append(liveness)
    # Keep only last 100 samples
    if len(sess["liveness_samples"]) > 100:
        sess["liveness_samples"] = sess["liveness_samples"][-100:]

    return FrameResponse(
        liveness_score=liveness,
        face_detected=face_detected,
        movement_detected=movement_detected,
        frame_diff_score=round(frame_diff_score, 4),
        bounding_box=BoundingBox(**bbox) if bbox else None,
        debug={"img_shape": list(img_bgr.shape), "timestamp": last_frame_time},
    )


@app.post("/process-text", response_model=TextResponse)
async def process_text(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    intent  = classify_intent(req.text)
    replies = ONBOARDING_RESPONSES.get(intent, ONBOARDING_RESPONSES["default"])
    reply   = random.choice(replies)

    sess_id = req.session_id or str(uuid.uuid4())
    sess    = get_or_create_session(sess_id)
    sess["messages"].append({"role": "user",      "text": req.text, "ts": time.time()})
    sess["messages"].append({"role": "assistant",  "text": reply,    "ts": time.time()})
    sess["intents"].append(intent)

    return TextResponse(
        reply=reply,
        intent=intent,
        confidence=round(random.uniform(0.82, 0.99), 2),
        session_id=sess_id,
    )


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
    )


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    sessions.pop(session_id, None)
    return {"deleted": session_id}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AI Onboarding Backend", "version": "1.1.0"}
