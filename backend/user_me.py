"""
Resolve authenticated user from video-session JWT (cookie or Bearer) + Neon DB.
Uses the same JWT_SECRET and DB as kyc_backend.
"""

import os
import uuid
from typing import Optional

import jwt
from fastapi import Cookie, Header, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

if not hasattr(jwt, "encode"):
    raise ImportError(
        "Install PyJWT: pip install PyJWT (and pip uninstall jwt if the wrong package is present)"
    )

JWT_SECRET = os.getenv("JWT_SECRET", "dev-change-me-use-strong-secret")
JWT_ALGORITHM = "HS256"
COOKIE_NAME = "video_session_token"

DATABASE_URL = os.getenv("NEON_DB_URL")
_engine: Optional[Engine] = None
if DATABASE_URL:
    _engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def _decode_token(raw: str) -> dict:
    return jwt.decode(raw, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def get_me(
    authorization: Optional[str] = Header(None),
    video_session_token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME),
):
    """
    Returns KYC user + video_session rows for the JWT issued after Aadhaar verification.
    Token source (first match): HttpOnly cookie `video_session_token`, or `Authorization: Bearer <jwt>`.
    """
    token = video_session_token
    if not token and authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = _decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
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

    if not _engine:
        raise HTTPException(
            status_code=503,
            detail="Database not configured (set NEON_DB_URL in backend .env)",
        )

    with _engine.connect() as conn:
        user_row = conn.execute(
            text(
                """
                SELECT id, full_name, email, mobile_number, aadhaar_number
                FROM kyc_users
                WHERE id = :uid
                """
            ),
            {"uid": user_id},
        ).mappings().first()

        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")

        vs_row = conn.execute(
            text(
                """
                SELECT user_name, created_at, is_completed
                FROM video_session
                WHERE session_id = CAST(:sid AS uuid)
                """
            ),
            {"sid": str(sid)},
        ).mappings().first()

        if not vs_row:
            raise HTTPException(status_code=404, detail="Video session not found")

    aadhaar = user_row["aadhaar_number"] or ""
    masked = "********" + aadhaar[-4:] if len(aadhaar) >= 4 else "****"
    created = vs_row["created_at"]
    created_iso = created.isoformat() if hasattr(created, "isoformat") else str(created)

    return {
        "user_id": user_row["id"],
        "full_name": user_row["full_name"],
        "email": user_row["email"],
        "mobile_number": user_row["mobile_number"],
        "session_id": str(sid),
        "video_session": {
            "user_name": vs_row["user_name"],
            "created_at": created_iso,
            "is_completed": bool(vs_row["is_completed"]),
        },
        "aadhaar_masked": masked,
    }
