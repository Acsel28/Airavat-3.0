@echo off
REM Quick Start - Run AIRAVAT with Streaming & Hold-to-Talk (Windows)

echo.
echo 🚀 Starting AIRAVAT Backend with Streaming Support...
echo.

REM Navigate to backend
cd backend

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install/upgrade dependencies
echo Installing dependencies...
python -m pip install -q --upgrade pip
pip install -q fastapi uvicorn google-genai python-multipart

echo ✓ Backend dependencies ready
echo.

REM Start backend on port 8000
echo 📡 Starting FastAPI server (port 8000)...
echo.
echo Access backend at: http://localhost:8000
echo Docs at: http://localhost:8000/docs
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

REM To run frontend in another terminal:
REM cd frontend
REM npm run dev
REM Then access at http://localhost:5173
