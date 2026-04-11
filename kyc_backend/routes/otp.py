from fastapi import APIRouter
from pydantic import BaseModel
from services.otp_service import generate_otp, send_otp_email, store_otp, verify_otp

router = APIRouter()

class OTPRequest(BaseModel):
    email: str

class OTPVerify(BaseModel):
    email: str
    otp: str


@router.post("/send-otp")
def send_otp(req: OTPRequest):
    otp = generate_otp()
    store_otp(req.email, otp)

    success = send_otp_email(req.email, otp)

    if not success:
        return {"status": "failed", "message": "Email failed"}

    return {"status": "success", "message": "OTP sent"}


@router.post("/verify-otp")
def verify(req: OTPVerify):
    if verify_otp(req.email, req.otp):
        return {"status": "success", "message": "OTP verified"}
    else:
        return {"status": "failed", "message": "Invalid OTP"}