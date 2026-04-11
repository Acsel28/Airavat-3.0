from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
from routes.otp import router as otp_router
from routes.aadhaar_verification import router as aadhar_router
from routes.pan_verification import router as pan_router
from routes.kyc_submission import router as kyc_submission_router

app = FastAPI()

# Set credentials
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'vision_key.json'

# Include routes
app.include_router(aadhar_router)
app.include_router(pan_router)
app.include_router(otp_router)
app.include_router(kyc_submission_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)