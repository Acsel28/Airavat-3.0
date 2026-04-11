from fastapi import APIRouter, UploadFile, File, Form
from services.pan_service import process_pan

router = APIRouter()

@router.post("/verify-pan")
async def verify_pan(input: str = Form(...), file: UploadFile = File(...)):
    file_bytes = await file.read()

    print("\n" + "="*60)
    print("📥 PAN VERIFICATION REQUEST RECEIVED")
    print("="*60)
    print(f"🔹 User Name: {input}")
    print(f"🔹 File Name: {file.filename}")
    print(f"🔹 File Size: {len(file_bytes)} bytes")
    print(f"🔹 File Content Type: {file.content_type}")
    print("="*60)

    details = process_pan(file_bytes)
    
    print("\n📤 EXTRACTED DETAILS FROM OCR:")
    print("="*60)
    print(f"🔹 Extracted Name: {details.get('name')}")
    print(f"🔹 PAN Number: {details.get('pan_number')}")
    print(f"🔹 Father's Name: {details.get('father_name')}")
    print("="*60)

    first_name = details["name"].split()[0] if details["name"] else ""
    if details["name"] and len(details["name"].split()) == 2:
        last_name = details["name"].split()[1]
    elif details["name"] and len(details["name"].split()) > 2:
        last_name = details["name"].split()[-1]
    father_name = details["father_name"].split()[0] if details["father_name"] else ""
    full_name = first_name + " " + father_name + " " + last_name
    
    uppercase_input = input.upper()
    
    print(f"\n✅ NAME MATCHING:")
    print(f"   Expected: {uppercase_input}")
    print(f"   Extracted: {full_name}")
    
    if full_name != uppercase_input:
        print(f"\n❌ NAME MISMATCH!")
        print("="*60 + "\n")
        return {
            "status": "failed",
            "message": "Name does not match the PAN details."
        }
    
    print(f"\n✅ VERIFICATION SUCCESSFUL!")
    print("="*60 + "\n")
    
    return {    
        "status": "success",
        "data": details
    }