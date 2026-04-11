# 🤖 AI Video Onboarding System – MVP

A full-stack AI onboarding assistant with:
- **Live webcam feed** with liveness detection (face + motion via MediaPipe)
- **Animated AI avatar** that reacts to speaking / listening / idle states
- **Voice interaction** via Web Speech API (mic → transcription → TTS)
- **FastAPI backend** with OpenCV + MediaPipe liveness scoring
- **Clean dark UI** built with React + Vite + Tailwind CSS

---

## 📁 Project Structure

```
project/
├── backend/
│   ├── main.py           # FastAPI app — /analyze-frame + /process-text
│   ├── requirements.txt  # Python deps
│   └── start.sh          # One-command start
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                      # Root layout & state wiring
│   │   ├── main.jsx                     # React entry
│   │   ├── index.css                    # Tailwind + custom keyframes
│   │   └── components/
│   │       ├── AIAvatar.jsx             # Animated SVG face (idle/listening/speaking)
│   │       ├── WebcamFeed.jsx           # getUserMedia + frame capture every 2s
│   │       ├── LivenessPanel.jsx        # Score gauge + indicator rows
│   │       └── VoiceChat.jsx            # Web Speech API + TTS + message log
│   ├── index.html
│   ├── vite.config.js                   # Proxies /analyze-frame → :8000
│   ├── tailwind.config.js
│   ├── package.json
│   └── start.sh
│
└── README.md
```

---

## 🚀 Quick Start

You need **two terminals** — one for the backend, one for the frontend.

### Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.9 – 3.11 |
| pip | latest |
| Node.js | 18+ |
| npm | 9+ |
| Chrome/Edge | latest (for Web Speech API) |

---

### Terminal 1 – Backend

```bash
cd backend
chmod +x start.sh
./start.sh
```

Or manually:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be at: `http://localhost:8000`  
Swagger docs: `http://localhost:8000/docs`

---

### Terminal 2 – Frontend

```bash
cd frontend
chmod +x start.sh
./start.sh
```

Or manually:

```bash
cd frontend
npm install
npm run dev
```

Frontend will be at: `http://localhost:5173`

---

## 🔬 How It Works

### Liveness Detection (`/analyze-frame`)

Every 2 seconds the frontend captures a JPEG frame from the webcam via `<canvas>` and sends it as base64 to the backend.

The backend computes a **liveness score (0–1)**:

| Signal | Weight | Logic |
|--------|--------|-------|
| Face detected | +0.40 | MediaPipe FaceDetection |
| Movement detected | +0.30 | Frame diff threshold > 1% |
| Frame diff score | +0.30 | Normalised mean-abs-diff |

Final score is multiplied by 100 for display (0–100).

### Voice Onboarding (`/process-text`)

1. User presses and holds the **mic button**
2. Browser transcribes speech via `SpeechRecognition`
3. Transcript POSTed to `/process-text`
4. Backend classifies intent (greeting / name / role / etc.) and picks a response
5. Frontend speaks the response via `SpeechSynthesisUtterance`
6. Avatar animates: **idle → listening → speaking → idle**

> In production, swap the mock classifier in `main.py → classify_intent()` for a real LLM call (OpenAI, Claude API, etc.).

---

## 🌐 API Reference

### `POST /analyze-frame`

```json
// Request
{ "image": "data:image/jpeg;base64,/9j/4AAQ..." }

// Response
{
  "liveness_score": 0.823,
  "face_detected": true,
  "movement_detected": true,
  "frame_diff_score": 0.0341,
  "debug": { "img_shape": [480, 640, 3], "timestamp": 1718000000.0 }
}
```

### `POST /process-text`

```json
// Request
{ "text": "Hi, my name is Alex", "session_id": "user-001" }

// Response
{
  "reply": "Nice to meet you Alex! What role are you joining us in?",
  "intent": "name",
  "confidence": 0.94
}
```

---

## 🛠 Customisation

| What | Where |
|------|-------|
| Swap mock LLM with real API | `backend/main.py → process_text()` |
| Change capture interval | `frontend/src/components/WebcamFeed.jsx → CAPTURE_INTERVAL_MS` |
| Tune liveness thresholds | `backend/main.py → compute_liveness()` |
| Change avatar colours/style | `frontend/src/components/AIAvatar.jsx` |
| Add more onboarding dialogue | `backend/main.py → ONBOARDING_RESPONSES` |

---

## ⚠️ Notes

- **Web Speech API** requires Chrome or Edge (not supported in Firefox/Safari without polyfill)
- Camera permissions must be granted in the browser
- The Vite dev server proxies `/analyze-frame` and `/process-text` to `localhost:8000` — no CORS issues in dev
- MediaPipe model downloads ~5 MB on first run
