from fastapi import APIRouter, UploadFile, File, Form
from services.aadhaar_service import process_aadhaar

router = APIRouter()

@router.post("/verify-aadhaar")
async def verify_aadhaar(string: str = Form(...), file: UploadFile = File(...)):
    file_bytes = await file.read()

    print("\n" + "="*60)
    print("📥 AADHAAR VERIFICATION REQUEST RECEIVED")
    print("="*60)
    print(f"🔹 User Name: {string}")
    print(f"🔹 File Name: {file.filename}")
    print(f"🔹 File Size: {len(file_bytes)} bytes")
    print(f"🔹 File Content Type: {file.content_type}")
    print("="*60)

    details = process_aadhaar(file_bytes)
    
    print("\n📤 EXTRACTED DETAILS FROM OCR:")
    print("="*60)
    print(f"🔹 Extracted Name: {details.get('name')}")
    print(f"🔹 Aadhaar Number: {details.get('aadhaar_number')}")
    print(f"🔹 DoB: {details.get('dob')}")
    print("="*60)

    if details.get("name") and details["name"].lower() != string.lower():
        print(f"\n❌ NAME MISMATCH!")
        print(f"   Expected: {string}")
        print(f"   Got: {details.get('name')}")
        print("="*60 + "\n")
        return {
            "status": "failed",
            "message": "Name does not match the Aadhaar details."
        }
    
    print(f"\n✅ VERIFICATION SUCCESSFUL!")
    print("="*60 + "\n")
    
    return {    
        "status": "success",
        "data": details
    }