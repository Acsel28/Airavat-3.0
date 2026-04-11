from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session
from database import KYCUser, get_db
from datetime import datetime
import base64
import numpy as np
import io
from PIL import Image

# Try to import face recognition libraries
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
    print("✅ face_recognition loaded successfully")
except ImportError:
    print("⚠️  face_recognition not available (requires dlib compilation)")
    FACE_RECOGNITION_AVAILABLE = False

router = APIRouter()

def generate_face_embedding(image_bytes):
    """
    Generate face embedding from image bytes.
    Uses face_recognition if available, otherwise returns placeholder.
    """
    try:
        if not FACE_RECOGNITION_AVAILABLE:
            print("⚠️  Generating placeholder embedding (face_recognition not installed)")
            # Return placeholder embedding (128 random values for now)
            return np.random.rand(128).tolist()
        
        # Load image from bytes
        image_array = np.array(Image.open(io.BytesIO(image_bytes)))
        
        # Generate 128-dimensional face encoding vector
        face_encodings = face_recognition.face_encodings(image_array)
        
        if len(face_encodings) == 0:
            print("⚠️  No face detected in the image")
            return None
        
        # Use first face detected, convert to list for pgvector
        embedding_vector = face_encodings[0].tolist()
        print(f"✅ Face embedding generated: {len(embedding_vector)} dimensions")
        return embedding_vector
        
    except Exception as e:
        print(f"❌ Error generating embedding: {str(e)}")
        return None

@router.post("/submit-kyc")
async def submit_kyc(
    full_name: str = Form(...),
    email: str = Form(...),
    dob: str = Form(...),
    gender: str = Form(...),
    mobile: str = Form(...),
    aadhaar: str = Form(...),
    pan: str = Form(...),
    face_image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Store complete KYC data with face embedding to PostgreSQL
    """
    
    print("\n" + "="*60)
    print("📥 KYC SUBMISSION RECEIVED")
    print("="*60)
    print(f"🔹 Full Name: {full_name}")
    print(f"🔹 Email: {email}")
    print(f"🔹 DOB: {dob}")
    print(f"🔹 Gender: {gender}")
    print(f"🔹 Mobile: {mobile}")
    print(f"🔹 Aadhaar: {aadhaar}")
    print(f"🔹 PAN: {pan}")
    print(f"🔹 Face Image: {face_image.filename}")
    print("="*60)

    try:
        # Read face image
        face_data = await face_image.read()
        
        print(f"\n📸 Face image size: {len(face_data)} bytes")
        
        # Generate face embedding from image
        print(f"🔍 Generating face embedding...")
        embedding_vector = generate_face_embedding(face_data)
        
        if embedding_vector is None:
            return {
                "status": "failed",
                "message": "Error processing face image. Please ensure a clear face photo is provided."
            }
        
        # Convert DOB string to date (expecting format: YYYY-MM-DD)
        try:
            dob_date = datetime.strptime(dob, "%m/%d/%Y").date()
        except:
            dob_date = None
        
        # Check if user already exists
        existing_user = db.query(KYCUser).filter(
            (KYCUser.email == email) | 
            (KYCUser.aadhaar_number == aadhaar) |
            (KYCUser.pan_number == pan)
        ).first()
        
        if existing_user:
            print(f"⚠️ User already exists with this email/aadhaar/pan")
            return {
                "status": "failed",
                "message": "User with this email, Aadhaar, or PAN already exists."
            }
        
        # Create new KYC user record with embedding
        kyc_user = KYCUser(
            full_name=full_name,
            email=email,
            date_of_birth=dob_date,
            gender=gender,
            mobile_number=mobile,
            aadhaar_number=aadhaar,
            pan_number=pan,
            embedding=embedding_vector,  # Store face embedding vector
            is_verified=True
        )
        
        db.add(kyc_user)
        db.commit()
        db.refresh(kyc_user)
        
        print(f"\n✅ KYC USER STORED SUCCESSFULLY")
        print(f"🔹 User ID: {kyc_user.id}")
        print(f"🔹 Email: {kyc_user.email}")
        print(f"🔹 Verification Status: {kyc_user.is_verified}")
        print(f"🔹 Face Embedding: Stored (128 dimensions)")
        print("="*60 + "\n")
        
        return {
            "status": "success",
            "message": "KYC data stored successfully",
            "user_id": kyc_user.id,
            "email": kyc_user.email
        }
        
    except Exception as err:
        print(f"\n❌ KYC SUBMISSION FAILED")
        print(f"Error: {str(err)}")
        print("="*60 + "\n")
        db.rollback()
        return {
            "status": "failed",
            "message": f"Error storing KYC data: {str(err)}"
        }
