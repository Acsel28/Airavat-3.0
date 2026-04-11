/**
 * TalkingAvatar – compact text input bar shown below the webcam feed.
 * In the new design this is a minimal strip (not a big card).
 */
import React from "react";

export default function TalkingAvatar({
  state = "idle",
  transcript = "",
  lastUserText = "",
  assistantReply = "",
  inputText = "",
  loading = false,
  sessionActive = false,
  onInputChange,
  onSubmitText,
  // unused in compact mode but kept for API compat
  avatarVideoUrl,
  sessionId,
  avatarProvider,
  onVideoPlay,
  onVideoEnd,
  onVideoError,
}) {
  const isSpeaking = state === "speaking";
  const isListening = state === "listening";

  return (
    <div className="kyc-avatar-strip">
      <div className="kyc-avatar-strip-status">
        <span
          className={`kyc-avatar-dot ${isSpeaking ? "kyc-avatar-dot--speaking" : isListening ? "kyc-avatar-dot--listening" : loading ? "kyc-avatar-dot--loading" : "kyc-avatar-dot--idle"}`}
        />
        <span className="kyc-avatar-strip-label">
          {isSpeaking
            ? "AI Speaking..."
            : isListening
              ? "Listening..."
              : loading
                ? "Processing..."
                : "AI Agent Ready"}
        </span>
      </div>

      <div className="kyc-avatar-strip-input">
        <input
          type="text"
          value={inputText}
          onChange={(e) => onInputChange?.(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSubmitText?.();
          }}
          placeholder="Say something or type here..."
          disabled={!sessionActive || loading || isSpeaking}
          className="kyc-strip-input"
        />
        <button
          onClick={() => onSubmitText?.()}
          disabled={
            !sessionActive || !inputText.trim() || loading || isSpeaking
          }
          className="kyc-strip-send"
        >
          {loading ? (
            <div className="kyc-strip-spinner" />
          ) : (
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          )}
        </button>
      </div>
    </div>
  );
}
