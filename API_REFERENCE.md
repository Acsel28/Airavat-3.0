# 🔌 API Reference - Streaming Endpoints

## Quick Reference Card

### Original Endpoint (Non-Streaming)
```
POST /loan/chat
Request: {
  "session_id": "string",
  "message": "string",
  "user_id": null | number,
  "kyc_profile": null | object
}
Response: {
  "reply": "string",
  "phase": "discovery|profiling|recommendation|negotiation|confirmation|done",
  "extracted_fields": {},
  "recommended_loan": {} | null,
  "offer": {} | null,
  "confidence": 0.0-1.0,
  "is_final": boolean,
  "turn_count": number
}
Behavior: ⚠️ Wait for full response before returning
```

### NEW: Streaming Endpoint ⭐
```
POST /loan/chat-stream
Request: {
  "session_id": "string",
  "message": "string",
  "user_id": null | number,
  "kyc_profile": null | object
}
Response: Server-Sent Events (stream)
  
Streaming Events:
{
  "type": "text",
  "chunk": "word ",
  "is_final": false
}
↓ (repeated for each word, ~50ms apart)
{
  "type": "metadata",
  "phase": "...",
  "extracted_fields": {...},
  "recommended_loan": {...},
  "offer": {...},
  "confidence": 0.8,
  "is_final": true,
  "turn_count": 5
}
↓
{
  "type": "done"
}

Behavior: ✅ Stream starts immediately, updates in real-time
```

---

## How Frontend Handles Streaming

### Code Snippet
```javascript
const res = await fetch("/loan/chat-stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(payload)
});

const reader = res.body.getReader();
const decoder = new TextDecoder();
let fullReply = "";

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const text = decoder.decode(value);
  const lines = text.split("\n");
  
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const event = JSON.parse(line.substring(6));
      
      if (event.type === "text") {
        fullReply += event.chunk;
        setAssistantReply(fullReply);  // Update UI
      } else if (event.type === "metadata") {
        // Handle metadata (phase, extracted fields, etc.)
      }
    }
  }
}
```

---

## Frontend Usage

### In App.jsx
```javascript
// Call streaming endpoint
const res = await fetch("/loan/chat-stream", {
  method: "POST",
  body: JSON.stringify({
    session_id, message, user_id, kyc_profile
  })
});

// Handle streaming response
const reader = res.body.getReader();
// ... (see code snippet above)
```

### In VoiceChat.jsx
```javascript
// Mic component handles recording
const startListening = () => {
  recognition.continuous = true;  // Don't auto-stop
  // ... capture speech
};

const stopListening = () => {
  recognition.stop();  // Stop when user releases
  // ... send message
};
```

---

## Error Handling

### SSE Error Event
```
{
  "type": "error",
  "message": "Error description"
}
```

### Frontend Catches
```javascript
} catch (err) {
  console.error("Streaming error:", err);
  // Show fallback message to user
  // Fall back to TTS
}
```

---

## Server-Sent Events (SSE) Specifics

### Headers Sent by Backend
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### Event Format
```
data: <JSON>\n\n
```

### Multiple events
```
data: {"type":"text","chunk":"Hello "}\n\n
data: {"type":"text","chunk":"world"}\n\n
data: {"type":"metadata","phase":"done"}\n\n
data: {"type":"done"}\n\n
```

---

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Streaming start | 500-1000ms | LLM generation + first event |
| Per chunk | 50ms | Configurable delay between words |
| Full response | Varies | Sum of all chunks (~2-4 words/sec) |
| Metadata receipt | 100ms+ | After text complete |
| Avatar API call | 1-2s | Separate from streaming |

---

## Testing the Endpoint

### cURL (Linux/Mac)
```bash
curl -X POST http://localhost:8000/loan/chat-stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-123",
    "message": "I need a home loan"
  }'
```

### PowerShell (Windows)
```powershell
$body = @{
    session_id = "test-123"
    message = "I need a home loan"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/loan/chat-stream" `
  -Method POST `
  -Headers @{"Content-Type"="application/json"} `
  -Body $body
```

### JavaScript (Browser)
```javascript
fetch("/loan/chat-stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    session_id: "test-123",
    message: "I need a home loan"
  })
}).then(res => res.body.getReader())
  .then(reader => {
    // Handle streaming as shown above
  });
```

---

## Configuration

### Adjust Streaming Speed
**File:** `backend/main.py` line ~1103
```python
await asyncio.sleep(0.05)  # 50ms between chunks
```

**Effect:**
- 0.01 = Very fast (10ms) = Machine-like
- 0.05 = Natural (50ms) = Reading pace ✓
- 0.1 = Slow (100ms) = Dramatic
- 0.2 = Very slow (200ms) = Too slow

### Adjust Chunk Size
**File:** `backend/main.py` line ~1098
```python
words = reply_text.split(" ")  # Currently: word-by-word
# Could change to:
# words = reply_text.split("  ")  # Clause-by-clause
# words = [reply_text[i:i+10] for i in range(0, len(reply_text), 10)]  # 10 chars
```

---

## Integration Points

### Frontend → Backend
1. VoiceChat captures speech
2. App.jsx calls `/loan/chat-stream`
3. Backend streams response
4. Frontend updates UI in real-time
5. Avatar API called with accumulated text

### Backend Components
1. FastAPI endpoint receives request
2. Calls existing `loan_chat()` function (no changes)
3. Streams response via SSE
4. Includes metadata when complete

### No Changes To:
- ✅ Gemini API integration
- ✅ Loan matching logic
- ✅ Database operations
- ✅ KYC verification
- ✅ Session management

---

## Backward Compatibility

### Old Code Still Works
```javascript
// This still works (non-streaming)
const res = await fetch("/loan/chat", {
  method: "POST",
  body: JSON.stringify(payload)
});
const data = await res.json();
```

### New Code (Streaming)
```javascript
// This is better (streaming)
const res = await fetch("/loan/chat-stream", {
  method: "POST",
  body: JSON.stringify(payload)
});
const reader = res.body.getReader();
// ... handle SSE
```

### Can Switch Anytime
- Both endpoints available
- No breaking changes
- Easy to A/B test

---

## Debugging

### Check if streaming works
**Browser DevTools → Network tab:**
1. Find `/loan/chat-stream` request
2. Click it
3. Go to "Response" tab
4. Should see multiple `data: {...}` lines

### Check if text is streaming
**Browser Console:**
```javascript
// Run this while response is streaming:
console.log($0.innerText)  // Will show partial text
```

### Check headers
**Network tab → Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
```

---

## Reusable Hook

### `useStreamingResponse.js`
```javascript
import { useStreamingResponse } from "@/hooks/useStreamingResponse";

function MyComponent() {
  const { fetchStream, cancel } = useStreamingResponse();
  
  const handleStream = async () => {
    await fetchStream(
      payload,
      (chunk) => console.log("Got:", chunk),      // onChunk
      (metadata) => console.log("Done:", metadata), // onMetadata
      (error) => console.error("Error:", error)   // onError
    );
  };
  
  return <button onClick={handleStream}>Stream!</button>;
}
```

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `404 /loan/chat-stream` | Endpoint doesn't exist | Update backend |
| Response not streaming | Frontend calling `/loan/chat` | Change to `/loan/chat-stream` |
| Text all appears at once | Network buffering | Check browser network settings |
| "connection closed" | Backend crash | Check server logs |
| High latency | Slow Gemini API | Check GEMINI_API_KEY rate limits |

---

## Summary

| Aspect | Old | New |
|--------|-----|-----|
| **Endpoint** | `/loan/chat` | `/loan/chat-stream` |
| **Response Type** | JSON | Server-Sent Events |
| **User Experience** | Wait for all + display | Stream chunks + display immediately |
| **Latency Feel** | 2-3s wait then see all | 1s wait then start seeing text |
| **Integration** | Simple JSON.parse() | Read stream + parse events |
| **Avatar Timing** | After response complete | Starts immediately |

---

📚 See also: `STREAMING_FEATURES_GUIDE.md` for user experience
