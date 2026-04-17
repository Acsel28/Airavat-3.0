#!/bin/bash
# Quick Start - Run AIRAVAT with Streaming & Hold-to-Talk

echo "🚀 Starting AIRAVAT Backend with Streaming Support..."

# Navigate to backend
cd backend

# Activate virtual environment (Windows-specific)
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
fi

# Install any missing dependencies
pip install -q fastapi uvicorn google-genai python-multipart

echo "✓ Backend dependencies ready"

# Start backend on port 8000
echo "📡 Starting FastAPI server (port 8000)..."
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal, run frontend:
# cd frontend
# npm run dev
