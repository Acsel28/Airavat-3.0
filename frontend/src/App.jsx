/**
 * App – root layout for AI Video Onboarding MVP.
 * Wires: webcam → liveness, voice chat → avatar + analytics + progress.
 */
import React, { useState, useCallback } from "react";
import WebcamFeed from "./components/WebcamFeed.jsx";
import LivenessPanel from "./components/LivenessPanel.jsx";
import AIAvatar from "./components/AIAvatar.jsx";
import VoiceChat from "./components/VoiceChat.jsx";
import OnboardingProgress from "./components/OnboardingProgress.jsx";
import AnalyticsPanel from "./components/AnalyticsPanel.jsx";

export default function App() {
  const makeSessionId = () =>
    globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  const [livenessData, setLivenessData] = useState(null);
  const [ageData, setAgeData] = useState(null);
  const [ageError, setAgeError] = useState("");
  const [avatarState, setAvatarState] = useState("idle");
  const [sessionActive, setSessionActive] = useState(false);
  const [sessionId, setSessionId] = useState(() => makeSessionId());
  const [isSecurityAlertActive, setIsSecurityAlertActive] = useState(false);
  const [securityAlertType, setSecurityAlertType] = useState(null);
  const [violationCount, setViolationCount] = useState(0);
  const [violationSecondsRemaining, setViolationSecondsRemaining] = useState(0);
  const [meetingTerminated, setMeetingTerminated] = useState(false);
  const [meetingEndMessage, setMeetingEndMessage] = useState(null);
  const [currentIntent, setCurrentIntent] = useState("greeting");
  const [completedIntents, setCompletedIntents] = useState([]);
  const [messageCount, setMessageCount] = useState(0);
  const [responseTimes, setResponseTimes] = useState([]);
  const [livenessSamples, setLivenessSamples] = useState([]);

  const handleLiveness = useCallback((data) => {
    setLivenessData(data);
    setLivenessSamples((prev) => {
      const next = [...prev, data.liveness_score];
      return next.length > 30 ? next.slice(-30) : next;
    });
  }, []);

  const handleIntent = useCallback((intent) => {
    setCurrentIntent(intent);
    setCompletedIntents((prev) =>
      prev.includes(intent) ? prev : [...prev, intent],
    );
  }, []);

  const handleResponseTime = useCallback((ms) => {
    setResponseTimes((prev) => {
      const next = [...prev, ms];
      return next.length > 20 ? next.slice(-20) : next;
    });
  }, []);

  const handleSecurityState = useCallback((data) => {
    const isViolation = Boolean(data?.violation_active);
    const isTerminated = Boolean(data?.meeting_terminated);
    setIsSecurityAlertActive(isViolation || isTerminated);
    setSecurityAlertType(data?.security_alert || null);
    setViolationCount(data?.violation_count || 0);
    setViolationSecondsRemaining(data?.violation_seconds_remaining || 0);
    setMeetingTerminated(isTerminated);
    setMeetingEndMessage(data?.meeting_end_message || null);
    if (isTerminated) {
      setSessionActive(false);
    }
  }, []);

  const toggleSession = () => {
    const nextActive = !sessionActive;
    if (!nextActive || meetingTerminated) {
      // Reset on end, and also reset when starting after a terminated meeting.
      setCompletedIntents([]);
      setCurrentIntent("greeting");
      setMessageCount(0);
      setResponseTimes([]);
      setLivenessSamples([]);
      setLivenessData(null);
      setIsSecurityAlertActive(false);
      setSecurityAlertType(null);
      setViolationCount(0);
      setViolationSecondsRemaining(0);
      setMeetingTerminated(false);
      setMeetingEndMessage(null);
      setSessionId(makeSessionId());
      setAgeData(null);
      setAgeError("");
    }
    setSessionActive(nextActive);
  };

  const livenessScore = livenessData
    ? Math.round(livenessData.liveness_score * 100)
    : 0;

  return (
    <div className="min-h-screen bg-ink font-body text-gray-200 flex flex-col">
      {/* Ambient blobs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(110,231,183,0.055) 0%, transparent 65%)",
          }}
        />
        <div
          className="absolute bottom-[-15%] right-[-5%] w-[500px] h-[500px] rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(129,140,248,0.065) 0%, transparent 65%)",
          }}
        />
        <div
          className="absolute top-[40%] left-[50%] w-[300px] h-[300px] rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(251,191,36,0.025) 0%, transparent 65%)",
          }}
        />
      </div>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="relative z-10 flex items-center justify-between px-6 lg:px-8 py-4 border-b border-border/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent2 flex items-center justify-center flex-shrink-0">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#0a0a0f"
              strokeWidth="2.5"
            >
              <circle cx="12" cy="8" r="4" />
              <path d="M20 21a8 8 0 1 0-16 0" />
            </svg>
          </div>
          <div>
            <span className="font-display font-bold text-lg tracking-tight leading-none block">
              on<span className="text-gradient">board</span>.ai
            </span>
            <span className="text-[10px] font-mono text-muted leading-none">
              AI-powered onboarding
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className={`hidden sm:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-full border transition-all ${
              sessionActive
                ? "border-accent/40 text-accent bg-accent/10"
                : "border-border text-muted bg-surface"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${sessionActive ? "bg-accent animate-pulse" : "bg-muted"}`}
            />
            {sessionActive ? "Session active" : "Ready"}
          </div>
          <button
            onClick={toggleSession}
            className="text-xs font-display font-semibold px-4 py-1.5 rounded-full transition-all cursor-pointer"
            style={{
              background: sessionActive
                ? "transparent"
                : "linear-gradient(135deg, #6ee7b7, #818cf8)",
              color: sessionActive ? "#f87171" : "#0a0a0f",
              border: sessionActive
                ? "1px solid rgba(248,113,113,0.6)"
                : "none",
            }}
          >
            {sessionActive ? "End Session" : "Start Session"}
          </button>
        </div>
      </header>

      {/* ── Main grid ──────────────────────────────────────────────────────── */}
      <main className="relative z-10 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-5 p-5 max-w-7xl mx-auto w-full">
        {/* Left: webcam + liveness bar */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-muted uppercase tracking-widest">
              Camera Feed
            </span>
            <div className="flex-1 h-px bg-border/50" />
            <span className="text-[10px] font-mono text-muted/50">
              2s analysis interval
            </span>
          </div>

          <WebcamFeed
            onLivenessUpdate={handleLiveness}
            onSecurityState={handleSecurityState}
            sessionId={sessionId}
            onAgeUpdate={setAgeData}
            onAgeError={setAgeError}
            active={sessionActive}
          />

          {/* Liveness bar */}
          <div className="card-glass rounded-xl px-5 py-3 flex items-center gap-4">
            <span className="text-xs font-mono text-muted whitespace-nowrap w-24">
              Liveness
            </span>
            <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${livenessScore}%`,
                  background:
                    livenessScore >= 70
                      ? "linear-gradient(90deg, #34d399, #6ee7b7)"
                      : livenessScore >= 40
                        ? "linear-gradient(90deg, #f59e0b, #fbbf24)"
                        : "linear-gradient(90deg, #ef4444, #f87171)",
                }}
              />
            </div>
            <span
              className="text-sm font-display font-bold w-8 text-right"
              style={{
                color:
                  livenessScore >= 70
                    ? "#6ee7b7"
                    : livenessScore >= 40
                      ? "#fbbf24"
                      : "#f87171",
              }}
            >
              {livenessScore}
            </span>
          </div>

          {/* Analytics – full width on desktop below camera */}
          <AnalyticsPanel
            sessionActive={sessionActive}
            messageCount={messageCount}
            responseTimes={responseTimes}
            livenessSamples={livenessSamples}
          />
        </div>

        {/* Right column */}
        <div className="flex flex-col gap-4">
          {/* Avatar */}
          <div className="card-glass rounded-2xl flex flex-col items-center py-7 gap-1">
            <span className="text-[10px] font-mono text-muted uppercase tracking-widest mb-3">
              AI Assistant
            </span>
            <AIAvatar state={avatarState} livenessScore={livenessScore} />
            <p className="text-xs text-center text-muted max-w-[190px] mt-7 font-body leading-relaxed">
              {avatarState === "speaking" && "Speaking your onboarding guide…"}
              {avatarState === "listening" && "Listening carefully…"}
              {avatarState === "idle" &&
                (sessionActive
                  ? "Hold mic or press Space to speak."
                  : "Start a session to begin.")}
            </p>
          </div>

          {/* Progress */}
          <OnboardingProgress
            currentIntent={currentIntent}
            completedIntents={completedIntents}
          />

          {/* Liveness detail */}
          <LivenessPanel
            data={livenessData}
            ageData={ageData}
            ageError={ageError}
          />

          {/* Voice chat */}
          <VoiceChat
            onStateChange={setAvatarState}
            onIntentDetected={handleIntent}
            onResponseTime={handleResponseTime}
            onMessageCountChange={setMessageCount}
            paused={isSecurityAlertActive || meetingTerminated}
            sessionId={sessionId}
          />
        </div>
      </main>

      {isSecurityAlertActive && (
        <div className="fixed inset-0 z-50 bg-ink/95 backdrop-blur-sm flex items-center justify-center p-6">
          <div className="max-w-xl w-full rounded-2xl border border-red-400/40 bg-red-500/10 p-8 text-center">
            <h2 className="text-2xl font-display font-bold text-red-300">
              Security Alert
            </h2>
            <p className="mt-3 text-base text-red-100">
              {meetingTerminated
                ? meetingEndMessage ||
                  "Meeting ended due to multiple identity violations."
                : "Face not valid. Please return to the camera within 30 seconds or the meeting will end."}
            </p>
            <p className="mt-2 text-xs font-mono text-red-200/80">
              Reason: {securityAlertType || "none"}
            </p>
            <p className="mt-4 text-xs text-red-100/80">
              {meetingTerminated
                ? "Start a new session to continue."
                : `Timer: ${violationSecondsRemaining}s · Violations: ${violationCount}/3`}
            </p>
          </div>
        </div>
      )}

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <footer className="relative z-10 text-center py-3 border-t border-border/30">
        <p className="text-[10px] font-mono text-muted/40">
          AI Video Onboarding MVP · MediaPipe · Web Speech API · FastAPI
        </p>
      </footer>
    </div>
  );
}
