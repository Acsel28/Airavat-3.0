import re
import uuid
import os
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import KYCUser, VideoSession, get_db
from services.jwt_auth import COOKIE_NAME, create_video_session_token, decode_video_session_token
from compare_embeddings import cosine_similarity, load_session_embeddings, to_float_vector

router = APIRouter()

FACE_MATCH_THRESHOLD = 0.92
BACKEND_EMBEDDING_DB_PATH = os.getenv(
    "BACKEND_EMBEDDING_DB_PATH",
    os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "authorized_embeddings.db")),
)


def _normalize_aadhaar(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _normalize_name(value: str) -> str:
    return " ".join((value or "").split()).lower()


def _build_face_match_payload(user_embedding, session_id: str):
    if user_embedding is None:
        return None

    try:
        user_vector = to_float_vector(user_embedding)
    except Exception:
        return None

    try:
        session_embeddings = load_session_embeddings(BACKEND_EMBEDDING_DB_PATH, session_id=session_id)
    except Exception:
        return {
            "session_id": session_id,
            "available": False,
            "reason": "backend_embedding_db_unavailable",
            "threshold": FACE_MATCH_THRESHOLD,
        }

    if not session_embeddings:
        return {
            "session_id": session_id,
            "available": False,
            "reason": "session_embedding_not_found",
            "threshold": FACE_MATCH_THRESHOLD,
        }

    try:
        similarity = cosine_similarity(user_vector, session_embeddings[0].vector)
    except Exception:
        return {
            "session_id": session_id,
            "available": False,
            "reason": "embedding_shape_mismatch",
            "threshold": FACE_MATCH_THRESHOLD,
        }

    percentage = round(similarity * 100, 2)
    return {
        "session_id": session_id,
        "available": True,
        "similarity": round(similarity, 6),
        "percentage": percentage,
        "is_match": similarity >= FACE_MATCH_THRESHOLD,
        "threshold": FACE_MATCH_THRESHOLD,
    }


def _serialize_embedding(user_embedding):
    if user_embedding is None:
        return None
    try:
        return to_float_vector(user_embedding).tolist()
    except Exception:
        return None


class VerifyAadhaarBody(BaseModel):
    session_id: str = Field(..., min_length=1)
    aadhaar_number: str = Field(..., min_length=1)


@router.post("/video-session/verify-aadhaar")
def verify_aadhaar_for_session(
    body: VerifyAadhaarBody,
    response: Response,
    db: Session = Depends(get_db),
):
    try:
        sid = uuid.UUID(body.session_id.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id")

    digits = _normalize_aadhaar(body.aadhaar_number)
    if len(digits) != 12:
        raise HTTPException(status_code=400, detail="Aadhaar must be 12 digits")

    vs = db.query(VideoSession).filter(VideoSession.session_id == sid).first()
    if not vs:
        raise HTTPException(status_code=404, detail="Session not found")

    candidates = db.query(KYCUser).filter(KYCUser.aadhaar_number.isnot(None)).all()
    matched: Optional[KYCUser] = None
    for u in candidates:
        if _normalize_aadhaar(u.aadhaar_number or "") != digits:
            continue
        if _normalize_name(u.full_name) != _normalize_name(vs.user_name):
            continue
        matched = u
        break

    if not matched:
        raise HTTPException(
            status_code=401,
            detail="Aadhaar does not match this session’s verified KYC record.",
        )

    token = create_video_session_token(matched.id, str(sid))
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/",
    )
    # Same JWT as cookie — lets other origins (e.g. AI backend on :8000) use Authorization: Bearer
    return {
        "status": "success",
        "message": "Verified",
        "user_id": matched.id,
        "access_token": token,
        "token_type": "bearer",
    }


@router.get("/get_me")
def get_me(
    db: Session = Depends(get_db),
    video_session_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
):
    if not video_session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_video_session_token(video_session_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    if payload.get("typ") != "video_session":
        raise HTTPException(status_code=401, detail="Invalid token type")

    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token subject")

    try:
        sid = uuid.UUID(payload.get("session_id", ""))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session in token")

    user = db.query(KYCUser).filter(KYCUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    vs = db.query(VideoSession).filter(VideoSession.session_id == sid).first()
    if not vs:
        raise HTTPException(status_code=404, detail="Video session not found")

    aadhaar = user.aadhaar_number or ""
    masked_aadhaar = (
        "********" + aadhaar[-4:]
        if len(aadhaar) >= 4
        else "****"
    )

    return {
        "user_id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "mobile_number": user.mobile_number,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "session_id": str(sid),
        "face_embedding": _serialize_embedding(user.embedding),
        "face_match": _build_face_match_payload(user.embedding, str(sid)),
        "video_session": {
            "user_name": vs.user_name,
            "created_at": vs.created_at.isoformat() if vs.created_at else None,
            "is_completed": vs.is_completed,
        },
        "aadhaar_masked": masked_aadhaar,
    }
