/**
 * App - KYC Loan Onboarding UI
 * Layout: top status bar, left data extraction panel, center webcam, right AI chat
 * Logic: merged with teammate's deriveStage / deriveDecision / fraudScore / provider tracking
 */
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import WebcamFeed from "./components/WebcamFeed.jsx";
import TalkingAvatar from "./components/TalkingAvatar.jsx";
import VoiceChat from "./components/VoiceChat.jsx";
import DataExtractionPanel from "./components/DataExtractionPanel.jsx";

// ─── Session ID ───────────────────────────────────────────────────────────────
function createSessionId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID)
    return crypto.randomUUID();
  return `session-${Date.now()}`;
}

// ─── Session Timer ────────────────────────────────────────────────────────────
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

// ─── Teammate logic helpers ───────────────────────────────────────────────────
function mapSecurityMessage(alertType) {
  switch (alertType) {
    case "multiple_faces":
      return "Multiple people detected. Please ensure only you are in the frame.";
    case "no_face":
      return "We can't see you. Please face the camera.";
    case "different_person":
      return "Face mismatch detected. Please verify identity.";
    case "meeting_ended":
      return "Session ended due to repeated violations.";
    default:
      return "";
  }
}

function deriveStage({
  sessionActive,
  data,
  messages,
  completedIntents,
  meetingTerminated,
}) {
  if (!sessionActive && messages.length === 0) return "intro";
  if (meetingTerminated) return "verification";
  if (!data?.is_verified || !data?.face_detected) return "verification";
  if (completedIntents.includes("done") || messages.length >= 6)
    return "decision";
  return "questioning";
}

function deriveDecision({
  livenessScore,
  violationCount,
  meetingTerminated,
  faceVerified,
}) {
  const approved =
    !meetingTerminated &&
    faceVerified &&
    livenessScore >= 65 &&
    violationCount < 2;
  return {
    approved,
    amount: approved ? 280000 : 120000,
    emi: approved ? 8240 : 5410,
    tenure: approved ? 36 : 24,
  };
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function App() {
  const [livenessData, setLivenessData] = useState(null);
  const [ageData, setAgeData] = useState(null);
  const [ageError, setAgeError] = useState("");
  const [avatarState, setAvatarState] = useState("idle");
  const [transcript, setTranscript] = useState("");
  const [lastUserText, setLastUserText] = useState("");
  const [assistantReply, setAssistantReply] = useState("");
  const [assistantProvider, setAssistantProvider] = useState(""); // teammate
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
  const [showDecisionWhy, setShowDecisionWhy] = useState(false); // teammate
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

  // ── Cleanup on unmount ──────────────────────────────────────────────────────
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

  // ── Teammate: derived computed values ───────────────────────────────────────
  const livenessScore = livenessData
    ? Math.round((livenessData.liveness_score || 0) * 100)
    : 0;

  const fraudScore = useMemo(() => {
    const penalty =
      violationCount * 18 +
      (livenessData?.security_alert && livenessData.security_alert !== "none"
        ? 22
        : 0);
    return Math.min(100, penalty);
  }, [livenessData, violationCount]);

  // Teammate's improved risk formula (weighted blend of liveness + fraud)
  const riskScore = useMemo(() => {
    const base = 100 - livenessScore;
    return Math.min(
      100,
      Math.max(0, Math.round(base * 0.55 + fraudScore * 0.45)),
    );
  }, [fraudScore, livenessScore]);

  const stage = useMemo(
    () =>
      deriveStage({
        sessionActive,
        data: livenessData,
        messages,
        completedIntents,
        meetingTerminated,
      }),
    [
      sessionActive,
      livenessData,
      messages,
      completedIntents,
      meetingTerminated,
    ],
  );

  const decision = useMemo(
    () =>
      deriveDecision({
        livenessScore,
        violationCount,
        meetingTerminated,
        faceVerified: Boolean(livenessData?.is_verified),
      }),
    [livenessData, livenessScore, meetingTerminated, violationCount],
  );

  const decisionReady = stage === "decision";
  const securityMessage = mapSecurityMessage(securityAlertType);

  // Derived UI-only helpers (our design)
  const riskColor =
    riskScore < 30 ? "#22c55e" : riskScore < 60 ? "#f59e0b" : "#ef4444";
  const deviceVerified = livenessData?.is_verified ?? false;
  const livenessOk = livenessScore >= 70;

  // ── Handlers ────────────────────────────────────────────────────────────────
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

  // Teammate: stamps timestamp on every message
  const appendMessage = useCallback((message) => {
    setMessages((prev) => {
      const next = [...prev, { ...message, timestamp: Date.now() }];
      setMessageCount(next.length);
      return next;
    });
  }, []);

  // Our: parse extracted KYC fields from conversation
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

  // ── TTS ─────────────────────────────────────────────────────────────────────
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
    utterance.onstart = () => setAvatarState("speaking");
    utterance.onend = () => setAvatarState("idle");
    utterance.onerror = () => setAvatarState("idle");
    synth.speak(utterance);
  }, []);

  // Teammate: simplified — Gemini handles text, browser handles audio fallback
  const speakReply = useCallback(
    async (text) => {
      if (!text) {
        setAvatarState("idle");
        return;
      }
      speakReplyFallback(text);
    },
    [speakReplyFallback],
  );

  // ── Submit ───────────────────────────────────────────────────────────────────
  const submitText = useCallback(
    async (providedText) => {
      const text = (providedText ?? inputText).trim();
      if (!text || loading || !sessionActive) return;

      setLoading(true);
      setTranscript("");
      setLastUserText(text);
      setAssistantReply("");
      setAssistantProvider(""); // teammate
      setAvatarVideoUrl("");
      setInputText("");
      appendMessage({ role: "user", text });

      // Our: inline loan keyword extraction from user speech
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
        setAssistantProvider(data.provider || ""); // teammate
        handleIntent(data.intent);
        parseExtractedData(data.reply, data.intent);

        // Teammate: includes provider in message payload
        appendMessage({
          role: "ai",
          text: data.reply,
          intent: data.intent,
          provider: data.provider,
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
        } catch (avatarErr) {
          console.warn(
            "D-ID talk unavailable, using audio fallback:",
            avatarErr,
          );
          setAvatarVideoUrl("");
          await speakReply(data.reply);
        }
      } catch (err) {
        console.error("Assistant error:", err);
        const fallback =
          "Sorry, I had trouble responding just now. Please try again.";
        setAssistantReply(fallback);
        setAssistantProvider("fallback"); // teammate
        appendMessage({ role: "ai", text: fallback, provider: "fallback" });
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

  // ── Toggle session ───────────────────────────────────────────────────────────
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
      setMessages([]);
      setLivenessData(null);
      setAgeData(null);
      setAgeError("");
      setAvatarState("idle");
      setTranscript("");
      setLastUserText("");
      setAssistantReply("");
      setAssistantProvider(""); // teammate
      setAvatarVideoUrl("");
      setInputText("");
      setLoading(false);
      setIsSecurityAlertActive(false);
      setSecurityAlertType("none");
      setViolationCount(0);
      setViolationSecondsRemaining(0);
      setMeetingTerminated(false);
      setMeetingEndMessage("");
      setShowDecisionWhy(false); // teammate
      setSessionId(createSessionId());
      setExtractedData({
        fullName: null,
        age: null,
        monthlyIncome: null,
        loanPurpose: null,
      });
    }
    setSessionActive((v) => !v);
  };

  // ────────────────────────────────────────────────────────────────────────────
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

      {/* ── Teammate: inline security banner (non-blocking, inside layout flow) ── */}
      {isSecurityAlertActive && !meetingTerminated && (
        <div className="kyc-security-banner">
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <div>
            <strong>Attention needed</strong>
            {securityMessage && <span> — {securityMessage}</span>}
          </div>
          <span className="kyc-banner-meta">
            Violations {violationCount}/3 · timer {violationSecondsRemaining}s
          </span>
        </div>
      )}

      {/* ── Main 3-column Layout ── */}
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

            {/* AI Agent overlay card */}
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
              {/* Teammate: stage indicator badge on the agent card */}
              {stage !== "intro" && (
                <div className="kyc-agent-stage">{stage}</div>
              )}
            </div>
          </div>

          {/* Bottom text input strip */}
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

      {/* ── Teammate: Decision Modal — styled to our KYC light theme ── */}
      {decisionReady && (
        <div className="kyc-alert-overlay">
          <div className="kyc-decision-card">
            <div className="kyc-decision-header">
              <div>
                <p className="kyc-decision-eyebrow">Decision Ready</p>
                <h2
                  className={`kyc-decision-title ${decision.approved ? "kyc-decision-title--approved" : "kyc-decision-title--review"}`}
                >
                  {decision.approved
                    ? "Approved with conditions"
                    : "Further review recommended"}
                </h2>
                <p className="kyc-decision-desc">
                  {decision.approved
                    ? "The onboarding signals are strong enough to present a preliminary offer. Review the terms below and continue."
                    : "We need a little more verification confidence before locking the final terms. You can still review the provisional structure."}
                </p>
              </div>
              <div className="kyc-decision-stage-badge">
                <p className="kyc-decision-stage-label">Current Stage</p>
                <p className="kyc-decision-stage-value">{stage}</p>
              </div>
            </div>

            <div className="kyc-decision-grid">
              <div className="kyc-decision-stat">
                <p className="kyc-decision-stat-label">Loan Amount</p>
                <p className="kyc-decision-stat-value">
                  ₹{decision.amount.toLocaleString("en-IN")}
                </p>
              </div>
              <div className="kyc-decision-stat">
                <p className="kyc-decision-stat-label">Estimated EMI</p>
                <p className="kyc-decision-stat-value">
                  ₹{decision.emi.toLocaleString("en-IN")}
                </p>
              </div>
              <div className="kyc-decision-stat">
                <p className="kyc-decision-stat-label">Tenure</p>
                <p className="kyc-decision-stat-value">
                  {decision.tenure} months
                </p>
              </div>
            </div>

            <div className="kyc-decision-actions">
              <button className="kyc-decision-btn kyc-decision-btn--accept">
                Accept Offer
              </button>
              <button className="kyc-decision-btn kyc-decision-btn--negotiate">
                Negotiate
              </button>
              <button
                className="kyc-decision-btn kyc-decision-btn--why"
                onClick={() => setShowDecisionWhy((v) => !v)}
              >
                Why this decision?
              </button>
            </div>

            {showDecisionWhy && (
              <div className="kyc-decision-why">
                <div className="kyc-why-card">
                  <p className="kyc-why-label">Income Verification</p>
                  <p className="kyc-why-text">
                    Question flow completed with stable session confidence and
                    response consistency.
                  </p>
                </div>
                <div className="kyc-why-card">
                  <p className="kyc-why-label">Credit Score Proxy</p>
                  <p className="kyc-why-text">
                    Financial discussion stage reached with no critical
                    conversation blockers.
                  </p>
                </div>
                <div className="kyc-why-card">
                  <p className="kyc-why-label">Fraud Signals</p>
                  <p className="kyc-why-text">
                    Risk score {riskScore}% with {violationCount} recorded
                    violation events.
                  </p>
                </div>
                <div className="kyc-why-card">
                  <p className="kyc-why-label">Identity Match</p>
                  <p className="kyc-why-text">
                    {livenessData?.is_verified
                      ? "Verified against enrolled session face."
                      : "Identity confidence still needs more signal."}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Teammate: Meeting Terminated Modal (dismissible) ── */}
      {meetingTerminated && (
        <div className="kyc-alert-overlay">
          <div className="kyc-alert-card">
            <div className="kyc-alert-icon">🚫</div>
            <h2>Session Terminated</h2>
            <p>
              {meetingEndMessage || "Session ended due to repeated violations."}
            </p>
            <div className="kyc-alert-meta">
              <span>Start a new session to continue.</span>
            </div>
            <button
              className="kyc-alert-dismiss"
              onClick={() => {
                setMeetingTerminated(false);
                setIsSecurityAlertActive(false);
              }}
            >
              Dismiss
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
