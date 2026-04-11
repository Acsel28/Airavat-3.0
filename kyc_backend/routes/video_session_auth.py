import re
import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import KYCUser, VideoSession, get_db
from services.jwt_auth import COOKIE_NAME, create_video_session_token, decode_video_session_token

router = APIRouter()


def _normalize_aadhaar(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _normalize_name(value: str) -> str:
    return " ".join((value or "").split()).lower()


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
        "session_id": str(sid),
        "video_session": {
            "user_name": vs.user_name,
            "created_at": vs.created_at.isoformat() if vs.created_at else None,
            "is_completed": vs.is_completed,
        },
        "aadhaar_masked": masked_aadhaar,
    }
