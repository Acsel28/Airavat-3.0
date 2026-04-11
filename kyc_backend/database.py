import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

# Try to import pgvector support
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    print("⚠️  pgvector not installed. Install with: pip install pgvector")
    Vector = None

# Load environment variables from .env file
load_dotenv()

# Database URL from .env
DATABASE_URL = os.getenv("NEON_DB_URL")

# Create engine
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class KYCUser(Base):
    __tablename__ = "kyc_users"

    id = Column(Integer, primary_key=True, index=True)
    
    # Personal Details
    full_name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False, index=True)
    date_of_birth = Column(Date)
    gender = Column(Text)
    mobile_number = Column(String(15))
    
    # Identity Documents
    aadhaar_number = Column(String(20), unique=True, nullable=True, index=True)
    pan_number = Column(String(20), unique=True, nullable=True, index=True)
    
    # Face Embedding (pgvector VECTOR(128))
    embedding = Column(Vector(128), nullable=True) if Vector else Column(Text, nullable=True)
    
    # Status
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    """Database session dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

