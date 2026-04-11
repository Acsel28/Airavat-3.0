from fastapi import APIRouter, UploadFile, File
from services.aadhaar_service import process_aadhaar

router = APIRouter()

@router.post("/verify-aadhaar")
async def verify_aadhaar(string: str, file: UploadFile = File(...)):
    file_bytes = await file.read()

    details = process_aadhaar(file_bytes)
    if details["name"] != string:
        return {
            "status": "failed",
            "message": "Name does not match the Aadhaar details."
        }
    return {    
        "status": "success",
        "data": details
    }