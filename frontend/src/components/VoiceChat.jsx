/**
 * VoiceChat – right panel showing conversation with AI Assistant.
 * Styled to match the screenshot: white card, message bubbles, STT labels.
 */
import React, { useState, useEffect, useRef, useCallback } from "react";

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition;

export default function VoiceChat({
  messages,
  loading,
  sessionActive,
  onStateChange,
  onSubmitText,
  onTranscriptChange,
  avatarState,
  assistantReply,
}) {
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [supported, setSupported] = useState(true);
  const [inputText, setInputText] = useState("");

  const recognitionRef = useRef(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (!SpeechRecognition) setSupported(false);
  }, []);

  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const startListening = useCallback(() => {
    if (!SpeechRecognition || listening || !sessionActive || loading) return;
    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      setListening(true);
      setTranscript("");
      onTranscriptChange?.("");
      onStateChange?.("listening");
    };
    recognition.onresult = (e) => {
      let interim = "",
        final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const val = e.results[i][0].transcript;
        if (e.results[i].isFinal) final += val;
        else interim += val;
      }
      const next = final || interim;
      setTranscript(next);
      onTranscriptChange?.(next);
      if (final.trim()) {
        recognition.stop();
        onSubmitText?.(final.trim());
      }
    };
    recognition.onerror = () => {
      setListening(false);
      setTranscript("");
      onTranscriptChange?.("");
      onStateChange?.("idle");
    };
    recognition.onend = () => {
      setListening(false);
      setTranscript("");
      onTranscriptChange?.("");
    };
    recognition.start();
  }, [
    listening,
    loading,
    onStateChange,
    onSubmitText,
    onTranscriptChange,
    sessionActive,
  ]);

  const stopListening = () => recognitionRef.current?.stop();

  const handleSend = () => {
    if (!inputText.trim() || !sessionActive || loading) return;
    onSubmitText?.(inputText.trim());
    setInputText("");
  };

  const isSpeaking = avatarState === "speaking";

  return (
    <div className="kyc-chat-panel">
      {/* Header */}
      <div className="kyc-chat-header">
        <div className="kyc-chat-agent-avatar">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
          >
            <rect x="3" y="8" width="18" height="12" rx="2" />
            <path d="M8 8V6a4 4 0 0 1 8 0v2" />
            <circle cx="12" cy="14" r="2" />
          </svg>
        </div>
        <div className="kyc-chat-agent-info">
          <div className="kyc-chat-agent-name">AI Assistant</div>
          <div className="kyc-chat-agent-model">
            Neural Engine v4.2
            {loading && (
              <span className="kyc-chat-generating">
                {" "}
                · Generating Offer...
              </span>
            )}
          </div>
        </div>
        {loading && (
          <div className="kyc-chat-spinner">
            <div className="kyc-spinner" />
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="kyc-chat-messages" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="kyc-chat-empty">
            {sessionActive
              ? "Start speaking or type a message below."
              : "Start a session to begin your KYC verification."}
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`kyc-msg ${m.role === "user" ? "kyc-msg--user" : "kyc-msg--ai"}`}
          >
            {m.role === "user" && (
              <div className="kyc-msg-stt-label">
                <svg
                  width="10"
                  height="10"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
                STT
              </div>
            )}
            <div className="kyc-msg-bubble">{m.text}</div>
            {m.rt && <div className="kyc-msg-rt">{m.rt}ms</div>}
          </div>
        ))}

        {transcript && (
          <div className="kyc-msg kyc-msg--user kyc-msg--interim">
            <div className="kyc-msg-stt-label">
              <svg
                width="10"
                height="10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
              STT
            </div>
            <div className="kyc-msg-bubble kyc-msg-bubble--interim">
              {transcript}...
            </div>
          </div>
        )}

        {loading && (
          <div className="kyc-msg kyc-msg--ai">
            <div className="kyc-msg-bubble kyc-msg-bubble--typing">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="kyc-chat-input-area">
        <button
          className={`kyc-mic-btn ${listening ? "kyc-mic-btn--active" : ""}`}
          onMouseDown={startListening}
          onMouseUp={stopListening}
          onTouchStart={startListening}
          onTouchEnd={stopListening}
          disabled={loading || !sessionActive || !supported}
          title={supported ? "Hold to speak" : "Not supported in this browser"}
        >
          {listening && <span className="kyc-mic-ping" />}
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </button>

        <input
          className="kyc-chat-input"
          type="text"
          placeholder={
            sessionActive ? "Type a message..." : "Start session to chat"
          }
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend();
          }}
          disabled={!sessionActive || loading || isSpeaking}
        />

        <button
          className="kyc-send-btn"
          onClick={handleSend}
          disabled={
            !sessionActive || !inputText.trim() || loading || isSpeaking
          }
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
    </div>
  );
}
