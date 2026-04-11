from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from routes.otp import router as otp_router
from routes.aadhaar_verification import router as aadhar_router
from routes.pan_verification import router as pan_router
from routes.kyc_submission import router as kyc_submission_router
from routes.video_session_auth import router as video_session_auth_router

app = FastAPI()

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'vision_key.json'

_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost",
).split(",")
_cors_origins = [o.strip() for o in _cors_origins if o.strip()]

# Include routes
app.include_router(aadhar_router)
app.include_router(pan_router)
app.include_router(otp_router)
app.include_router(kyc_submission_router)
app.include_router(video_session_auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)