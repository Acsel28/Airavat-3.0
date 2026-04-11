"""
AI Video Onboarding System - FastAPI Backend
Handles liveness detection, AI text responses, and session tracking.
"""

import base64
import time
import uuid
import sqlite3
import json
import math
import numpy as np
import cv2
import mediapipe as mp
import face_recognition
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

# Realtime tuning knobs
FRAME_SCALE = 0.5
AUTHORIZED_COSINE_THRESHOLD = 0.92
EMBEDDING_DB_PATH = "authorized_embeddings.db"
VIOLATION_TIMEOUT_SECONDS = 30
MAX_VIOLATIONS = 3

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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "AI Onboarding Backend", "version": "1.1.0"}
