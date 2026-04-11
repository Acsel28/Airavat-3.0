/**
 * App - KYC Loan Onboarding UI
 * Layout: top status bar, left data extraction panel, center webcam, right AI chat
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import WebcamFeed from "./components/WebcamFeed.jsx";
import LivenessPanel from "./components/LivenessPanel.jsx";
import TalkingAvatar from "./components/TalkingAvatar.jsx";
import VoiceChat from "./components/VoiceChat.jsx";
import OnboardingProgress from "./components/OnboardingProgress.jsx";
import AnalyticsPanel from "./components/AnalyticsPanel.jsx";
import DataExtractionPanel from "./components/DataExtractionPanel.jsx";

function createSessionId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID)
    return crypto.randomUUID();
  return `session-${Date.now()}`;
}

function useSessionTimer(active) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(null);
  useEffect(() => {
    if (active) {
      startRef.current = Date.now();
      const t = setInterval(
        () => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)),
        1000,
      );
      return () => clearInterval(t);
    } else {
      setElapsed(0);
    }
  }, [active]);
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function App() {
  const [livenessData, setLivenessData] = useState(null);
  const [ageData, setAgeData] = useState(null);
  const [ageError, setAgeError] = useState("");
  const [avatarState, setAvatarState] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const [lastUserText, setLastUserText] = useState("");
  const [assistantReply, setAssistantReply] = useState("");
  const [avatarVideoUrl, setAvatarVideoUrl] = useState("");
  const [inputText, setInputText] = useState("");
  const [sessionId, setSessionId] = useState(createSessionId);
  const [sessionActive, setSessionActive] = useState(false);
  const [currentIntent, setCurrentIntent] = useState("greeting");
  const [completedIntents, setCompletedIntents] = useState([]);
  const [messageCount, setMessageCount] = useState(0);
  const [responseTimes, setResponseTimes] = useState([]);
  const [livenessSamples, setLivenessSamples] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isSecurityAlertActive, setIsSecurityAlertActive] = useState(false);
  const [securityAlertType, setSecurityAlertType] = useState("none");
  const [violationCount, setViolationCount] = useState(0);
  const [violationSecondsRemaining, setViolationSecondsRemaining] = useState(0);
  const [meetingTerminated, setMeetingTerminated] = useState(false);
  const [meetingEndMessage, setMeetingEndMessage] = useState("");
  // Extracted data from conversation
  const [extractedData, setExtractedData] = useState({
    fullName: null,
    age: null,
    monthlyIncome: null,
    loanPurpose: null,
  });

  const synthRef = useRef(
    typeof window !== "undefined" ? window.speechSynthesis : null,
  );
  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);
  const sessionTime = useSessionTimer(sessionActive);

  useEffect(() => {
    return () => {
      synthRef.current?.cancel();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = "";
      }
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    };
  }, []);

  const handleLiveness = useCallback((data) => {
    setLivenessData(data);
    setLivenessSamples((prev) => {
      const next = [...prev, data.liveness_score];
      return next.length > 30 ? next.slice(-30) : next;
    });
    const alert = data?.security_alert && data.security_alert !== "none";
    setIsSecurityAlertActive(Boolean(alert));
    setSecurityAlertType(data?.security_alert || "none");
    setViolationCount(data?.violation_count || 0);
    setViolationSecondsRemaining(data?.violation_seconds_remaining || 0);
    if (data?.meeting_terminated) {
      setMeetingTerminated(true);
      setMeetingEndMessage(
        data?.meeting_end_message ||
          "Meeting ended due to multiple identity violations.",
      );
      setSessionActive(false);
      setAvatarState("idle");
    }
  }, []);

  const handleSecurityState = useCallback((data) => {
    const alert = data?.security_alert && data.security_alert !== "none";
    setIsSecurityAlertActive(Boolean(alert));
    setSecurityAlertType(data?.security_alert || "none");
    setViolationCount(data?.violation_count || 0);
    setViolationSecondsRemaining(data?.violation_seconds_remaining || 0);
  }, []);

  const handleIntent = useCallback((intent) => {
    setCurrentIntent(intent);
    setCompletedIntents((prev) =>
      prev.includes(intent) ? prev : [...prev, intent],
    );
  }, []);

  const appendMessage = useCallback((message) => {
    setMessages((prev) => {
      const next = [...prev, message];
      setMessageCount(next.length);
      return next;
    });
  }, []);

  // Parse extracted fields from assistant replies
  const parseExtractedData = useCallback((text, intent) => {
    setExtractedData((prev) => {
      const next = { ...prev };
      if (intent === "name" && !next.fullName) {
        const m = text.match(/([A-Z][a-z]+ [A-Z][a-z]+)/);
        if (m) next.fullName = m[1];
      }
      if (intent === "experience" && !next.age) {
        const m = text.match(/(\d+)\s*year/i);
        if (m) next.age = parseInt(m[1]) + 22;
      }
      return next;
    });
  }, []);

  const speakReplyFallback = useCallback((text) => {
    const synth = synthRef.current;
    if (!synth || !text) {
      setAvatarState("idle");
      return;
    }
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.96;
    utterance.pitch = 1.02;
    utterance.volume = 1;
    const voices = synth.getVoices();
    const preferred = voices.find(
      (v) =>
        v.lang === "en-US" ||
        v.name.includes("Google") ||
        v.name.includes("Samantha"),
    );
    if (preferred) utterance.voice = preferred;
    utterance.onstart = () => setAvatarState("speaking");
    utterance.onend = () => setAvatarState("idle");
    utterance.onerror = () => setAvatarState("idle");
    synth.speak(utterance);
  }, []);

  const speakReply = useCallback(
    async (text) => {
      if (!text) {
        setAvatarState("idle");
        return;
      }
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current);
        audioUrlRef.current = null;
      }
      try {
        const res = await fetch("/api/speak", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text,
            voice: "marin",
            instructions: "Speak warmly and conversationally.",
            response_format: "wav",
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (!blob.size) throw new Error("Empty audio response");
        const audio = audioRef.current || new Audio();
        audioRef.current = audio;
        const url = URL.createObjectURL(blob);
        audioUrlRef.current = url;
        audio.src = url;
        audio.onplay = () => setAvatarState("speaking");
        audio.onended = () => setAvatarState("idle");
        audio.onerror = () => {
          setAvatarState("idle");
          speakReplyFallback(text);
        };
        await audio.play();
      } catch (err) {
        console.warn("Backend TTS unavailable:", err);
        speakReplyFallback(text);
      }
    },
    [speakReplyFallback],
  );

  const submitText = useCallback(
    async (providedText) => {
      const text = (providedText ?? inputText).trim();
      if (!text || loading || !sessionActive) return;
      setLoading(true);
      setTranscript("");
      setLastUserText(text);
      setAssistantReply("");
      setAvatarVideoUrl("");
      setInputText("");
      appendMessage({ role: "user", text });
      const startedAt = Date.now();
      try {
        const res = await fetch("/process-text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, session_id: sessionId }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const responseTime = Date.now() - startedAt;
        setResponseTimes((prev) => {
          const next = [...prev, responseTime];
          return next.length > 20 ? next.slice(-20) : next;
        });
        setAssistantReply(data.reply);
        handleIntent(data.intent);
        parseExtractedData(data.reply, data.intent);
        // Extract loan data from user text
        if (
          text.toLowerCase().includes("loan") ||
          text.toLowerCase().includes("home") ||
          text.toLowerCase().includes("renovati")
        ) {
          setExtractedData((prev) => ({
            ...prev,
            loanPurpose: prev.loanPurpose || "Home Renovation",
          }));
        }
        if (text.match(/\d+[\.,]\d+\s*(lakh|lac|k)/i)) {
          const m = text.match(/(\d+[\.,]?\d*)\s*(lakh|lac)/i);
          if (m)
            setExtractedData((prev) => ({
              ...prev,
              monthlyIncome: prev.monthlyIncome || `₹${m[1]} lakhs`,
            }));
        }
        appendMessage({
          role: "ai",
          text: data.reply,
          intent: data.intent,
          rt: responseTime,
          suggestions: data.suggestions,
        });
        try {
          const avatarRes = await fetch("/api/avatar/talk", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: data.reply }),
          });
          if (!avatarRes.ok) throw new Error(`HTTP ${avatarRes.status}`);
          const avatarData = await avatarRes.json();
          setAvatarVideoUrl(avatarData.result_url || "");
        } catch {
          setAvatarVideoUrl("");
          await speakReply(data.reply);
        }
      } catch (err) {
        console.error("Assistant error:", err);
        const fallback = "Sorry, I had trouble responding. Please try again.";
        setAssistantReply(fallback);
        appendMessage({ role: "ai", text: fallback });
        setAvatarVideoUrl("");
        await speakReply(fallback);
      } finally {
        setLoading(false);
      }
    },
    [
      appendMessage,
      handleIntent,
      inputText,
      loading,
      parseExtractedData,
      sessionActive,
      sessionId,
      speakReply,
    ],
  );

  const toggleSession = () => {
    if (sessionActive) {
      synthRef.current?.cancel();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      setCurrentIntent("greeting");
      setCompletedIntents([]);
      setMessageCount(0);
      setResponseTimes([]);
      setLivenessSamples([]);
      setLivenessData(null);
      setAgeData(null);
      setAgeError("");
      setAvatarState("idle");
      setTranscript("");
      setLastUserText("");
      setAssistantReply("");
      setAvatarVideoUrl("");
      setInputText("");
      setMessages([]);
      setLoading(false);
      setSessionId(createSessionId());
      setIsSecurityAlertActive(false);
      setSecurityAlertType("none");
      setViolationCount(0);
      setViolationSecondsRemaining(0);
      setMeetingTerminated(false);
      setMeetingEndMessage("");
      setExtractedData({
        fullName: null,
        age: null,
        monthlyIncome: null,
        loanPurpose: null,
      });
    }
    setSessionActive((v) => !v);
  };

  const livenessScore = livenessData
    ? Math.round(livenessData.liveness_score * 100)
    : 0;
  const riskScore = livenessScore > 0 ? Math.max(0, 100 - livenessScore) : 0;
  const riskColor =
    riskScore < 30 ? "#22c55e" : riskScore < 60 ? "#f59e0b" : "#ef4444";
  const deviceVerified = livenessData?.is_verified ?? false;
  const livenessOk = livenessScore >= 70;

  return (
    <div className="kyc-root">
      {/* ── Top Status Bar ── */}
      <header className="kyc-topbar">
        <div className="kyc-topbar-left">
          <div className="kyc-logo">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
            >
              <rect x="3" y="3" width="18" height="18" rx="3" />
              <path d="M9 12l2 2 4-4" />
            </svg>
            <span>
              KYC<strong>Verify</strong>
            </span>
          </div>
        </div>

        <div className="kyc-topbar-stats">
          <div className="kyc-stat">
            <span
              className={`kyc-dot ${sessionActive ? "kyc-dot--green" : "kyc-dot--gray"}`}
            />
            <span className="kyc-stat-label">Session</span>
            <span className="kyc-stat-value kyc-mono">{sessionTime}</span>
          </div>
          <div className="kyc-divider" />
          <div className="kyc-stat">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#6b7280"
              strokeWidth="2"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span className="kyc-stat-label">Risk</span>
            <div className="kyc-risk-bar">
              <div
                className="kyc-risk-fill"
                style={{ width: `${riskScore}%`, background: riskColor }}
              />
            </div>
            <span
              className="kyc-stat-value kyc-mono"
              style={{ color: riskColor }}
            >
              {riskScore}
            </span>
          </div>
          <div className="kyc-divider" />
          <div
            className={`kyc-stat ${deviceVerified ? "kyc-stat--success" : "kyc-stat--muted"}`}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="5" y="2" width="14" height="20" rx="2" />
              <path d="M12 18h.01" />
            </svg>
            <span>Device {deviceVerified ? "Verified" : "Unverified"}</span>
          </div>
          <div className="kyc-divider" />
          <div className="kyc-stat kyc-stat--muted">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
              <circle cx="12" cy="10" r="3" />
            </svg>
            <span>Mumbai, IN</span>
          </div>
          <div className="kyc-divider" />
          <div
            className={`kyc-stat ${livenessOk ? "kyc-stat--success" : "kyc-stat--warn"}`}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
            <span>Liveness {livenessOk ? "OK" : "Checking"}</span>
          </div>
          <div className="kyc-divider" />
          <div
            className={`kyc-stat kyc-violations ${violationCount > 0 ? "kyc-violations--active" : ""}`}
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>Violations: {violationCount}/3</span>
          </div>
        </div>

        <div className="kyc-topbar-right">
          <button
            className={`kyc-btn-session ${sessionActive ? "kyc-btn-session--end" : ""}`}
            onClick={toggleSession}
          >
            {sessionActive ? "End Session" : "Start Session"}
          </button>
        </div>
      </header>

      {/* ── Main Layout ── */}
      <main className="kyc-main">
        {/* Left: Data Extraction */}
        <aside className="kyc-sidebar-left">
          <DataExtractionPanel
            extractedData={extractedData}
            ageData={ageData}
            messages={messages}
          />
        </aside>

        {/* Center: Webcam + AI Agent overlay */}
        <section className="kyc-center">
          <div className="kyc-webcam-wrapper">
            <WebcamFeed
              onLivenessUpdate={handleLiveness}
              onSecurityState={handleSecurityState}
              onAgeUpdate={setAgeData}
              onAgeError={setAgeError}
              active={sessionActive}
              sessionId={sessionId}
            />

            {/* AI Agent overlay card (top-right of webcam) */}
            <div
              className={`kyc-agent-card ${avatarState === "speaking" ? "kyc-agent-card--speaking" : avatarState === "listening" ? "kyc-agent-card--listening" : ""}`}
            >
              <div className="kyc-agent-icon">
                <svg
                  width="22"
                  height="22"
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
              <div className="kyc-agent-label">AI Agent</div>
              <div className="kyc-agent-status">
                {avatarState === "speaking" ? (
                  <>
                    <span className="kyc-speaking-dot" />
                    {" Speaking..."}
                  </>
                ) : avatarState === "listening" ? (
                  <>
                    <span className="kyc-listening-dot" />
                    {" Listening..."}
                  </>
                ) : loading ? (
                  <>
                    <span className="kyc-thinking-dot" />
                    {" Thinking..."}
                  </>
                ) : (
                  <>
                    <span className="kyc-idle-dot" />
                    {" Ready"}
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Bottom controls */}
          <div className="kyc-center-controls">
            <TalkingAvatar
              state={avatarState}
              transcript={transcript}
              lastUserText={lastUserText}
              assistantReply={assistantReply}
              avatarVideoUrl={avatarVideoUrl}
              sessionId={sessionId}
              inputText={inputText}
              loading={loading}
              sessionActive={sessionActive}
              onInputChange={setInputText}
              onSubmitText={() => submitText()}
              onVideoPlay={() => setAvatarState("speaking")}
              onVideoEnd={() => setAvatarState("idle")}
            />
          </div>
        </section>

        {/* Right: Chat panel */}
        <aside className="kyc-sidebar-right">
          <VoiceChat
            messages={messages}
            loading={loading}
            sessionActive={sessionActive}
            onStateChange={setAvatarState}
            onSubmitText={submitText}
            onTranscriptChange={setTranscript}
            avatarState={avatarState}
            assistantReply={assistantReply}
          />
        </aside>
      </main>

      {/* Security Alert Overlay */}
      {isSecurityAlertActive && (
        <div className="kyc-alert-overlay">
          <div className="kyc-alert-card">
            <div className="kyc-alert-icon">⚠️</div>
            <h2>Security Alert</h2>
            <p>
              {meetingTerminated
                ? meetingEndMessage ||
                  "Meeting ended due to multiple identity violations."
                : securityAlertType === "multiple_faces"
                  ? "Multiple faces detected. Only one participant should be visible."
                  : "Face not valid. Please return to the camera within 30 seconds."}
            </p>
            <div className="kyc-alert-meta">
              <span>Reason: {securityAlertType || "none"}</span>
              {!meetingTerminated && (
                <span>
                  Timer: {violationSecondsRemaining}s · Violations:{" "}
                  {violationCount}/3
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
