from fastapi import APIRouter, UploadFile, File
from services.pan_service import process_pan

router = APIRouter()

@router.post("/verify-pan")
async def verify_pan(input: str, file: UploadFile = File(...)):
    file_bytes = await file.read()

    details = process_pan(file_bytes)
    first_name = details["name"].split()[0] if details["name"] else ""
    last_name = details["name"].split()[1] if details["name"] and len(details["name"].split()) > 1 else ""
    father_name = details["father_name"].split()[0] if details["father_name"] else ""
    full_name = first_name + " " + father_name + " " + last_name
    # print("Extracted Full Name:", full_name)
    Uppercase_input = input.upper()
    # print("Uppercase Input Name:", Uppercase_input)
    if full_name != Uppercase_input:
        return {
            "status": "failed",
            "message": "Name does not match the PAN details."
        }
    return {    
        "status": "success",
        "data": details
    }