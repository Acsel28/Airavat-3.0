import os
from datetime import datetime, timedelta, timezone

# Must be PyJWT (pip package name: PyJWT), not the unrelated PyPI package "jwt".
import jwt

if not hasattr(jwt, "encode"):
    raise ImportError(
        "Wrong 'jwt' module: uninstall the 'jwt' package and install PyJWT: "
        "pip uninstall jwt -y && pip install PyJWT"
    )

JWT_SECRET = os.getenv("JWT_SECRET", "dev-change-me-use-strong-secret")
JWT_ALGORITHM = "HS256"
COOKIE_NAME = "video_session_token"
TOKEN_EXPIRE_DAYS = 7


def create_video_session_token(user_id: int, session_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "session_id": session_id,
        "typ": "video_session",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=TOKEN_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_video_session_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
