/**
 * VoiceChat – Google Meet Style
 * Unmute to record, Mute to send
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
  avatarState,
}) {
  const [isMuted, setIsMuted] = useState(true);
  const [transcript, setTranscript] = useState("");
  const [supported, setSupported] = useState(true);

  const recognitionRef = useRef(null);
  const scrollRef = useRef(null);
  const finalTranscriptRef = useRef("");

  useEffect(() => {
    if (!SpeechRecognition) setSupported(false);
  }, []);

  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  // Auto start/stop recording based on mute state
  useEffect(() => {
    if (!isMuted && sessionActive && !loading) {
      startRecording();
    } else {
      stopRecording();
    }
  }, [isMuted, sessionActive, loading]);

  const startRecording = useCallback(() => {
    if (!SpeechRecognition || !sessionActive || loading) return;

    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    finalTranscriptRef.current = "";
    setTranscript("");
    onStateChange?.("listening");

    recognition.onstart = () => {
      console.log("🎤 Recording started");
    };

    recognition.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const val = e.results[i][0].transcript;
        if (e.results[i].isFinal) {
          finalTranscriptRef.current += val + " ";
        } else {
          interim += val;
        }
      }

      const displayText = (finalTranscriptRef.current + interim).trim();
      setTranscript(displayText);
    };

    recognition.onerror = (event) => {
      console.warn("Speech error:", event.error);
    };

    recognition.onend = () => {
      console.log("Recording ended");
    };

    try {
      recognition.start();
    } catch (e) {
      console.log("Recognition already started");
    }
  }, [sessionActive, loading, onStateChange]);

  const stopRecording = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {
        console.log("Recognition already stopped");
      }
    }

    // When muted, send the transcript if there's any
    if (isMuted && finalTranscriptRef.current.trim()) {
      const finalText = finalTranscriptRef.current.trim();
      console.log("📤 Sending:", finalText);

      setTranscript("");
      onStateChange?.("idle");

      // Send message
      onSubmitText?.(finalText);

      // Reset for next
      finalTranscriptRef.current = "";
    }
  }, [isMuted, onSubmitText, onStateChange]);

  const toggleMute = () => {
    setIsMuted((prev) => !prev);
  };

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
                · Processing...
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
              ? "Click unmute and start speaking"
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
                </svg>
                Unmuted
              </div>
            )}
            <div className="kyc-msg-bubble">{m.text}</div>
            {m.rt && <div className="kyc-msg-rt">{m.rt}ms</div>}
          </div>
        ))}

        {/* Show interim transcript if unmuted and recording */}
        {transcript && !isMuted && (
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
              </svg>
              Recording...
              <span className="kyc-recording-dot">●</span>
            </div>
            <div className="kyc-msg-bubble kyc-msg-bubble--interim">
              {transcript}
            </div>
          </div>
        )}

        {/* Typing indicator while waiting for response */}
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

      {/* Input Controls */}
      <div className="kyc-chat-input-area">
        <button
          className={`kyc-mute-btn ${isMuted ? "kyc-mute-btn--muted" : "kyc-mute-btn--unmuted"}`}
          onClick={toggleMute}
          disabled={!sessionActive || loading || !supported}
          title={isMuted ? "Click to unmute and speak" : "Click to mute and send"}
        >
          {isMuted ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M13 5v7h4V5h-4z"/>
              <path d="M1 1l22 22M5 5a7 7 0 0114 0v7a7 7 0 01-14 0"/>
              <line x1="1" y1="1" x2="23" y2="23" stroke="currentColor" strokeWidth="2"/>
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <path d="M12 19v3" />
              <path d="M8 22h8" />
            </svg>
          )}
        </button>

        <div className="kyc-mute-status">
          {isMuted ? "🔴 Muted" : "🟢 Unmuted"}
        </div>
      </div>
    </div>
  );
}
