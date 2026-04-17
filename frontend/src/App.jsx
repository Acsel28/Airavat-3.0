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
import LoanOfferModal from "./components/LoanOfferModal.jsx";

const KYC_API = import.meta.env.VITE_KYC_API_URL || "http://localhost:8001";
const APP_SESSION_ID_STORAGE_KEY = "app_onboarding_session_id";

// ─── Session ID ───────────────────────────────────────────────────────────────
function createSessionId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID)
    return crypto.randomUUID();
  return `session-${Date.now()}`;
}

function getInitialSessionId() {
  try {
    const saved = sessionStorage.getItem(APP_SESSION_ID_STORAGE_KEY);
    if (saved) return saved;
  } catch (_) {
    // Ignore storage failures (private mode, quota, etc).
  }
  return createSessionId();
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
  const currentYear = new Date().getFullYear();
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
  const [sessionId, setSessionId] = useState(getInitialSessionId);
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
    dateOfBirth: null,
    age: null,
    monthlyIncome: null,
    loanPurpose: null,
    faceMatchLabel: null,
    faceMatchPercentage: null,
  });
  const [sessionUserName, setSessionUserName] = useState(null);

  // ── Loan Agent State ─────────────────────────────────────────────────────
  const [loanPhase, setLoanPhase] = useState("discovery");
  const [currentOffer, setCurrentOffer] = useState(null);
  const [ciblScore, setCiblScore] = useState(null);
  const [showOfferModal, setShowOfferModal] = useState(false);
  const [loanApproved, setLoanApproved] = useState(false);
  const [loanExtractedFields, setLoanExtractedFields] = useState({});
  const [loanApproving, setLoanApproving] = useState(false);
  const kycProfileRef = useRef(null); // cached from get_me

  const synthRef = useRef(
    typeof window !== "undefined" ? window.speechSynthesis : null,
  );
  const audioRef = useRef(null);
  const audioUrlRef = useRef(null);
  const sessionTime = useSessionTimer(sessionActive);

  useEffect(() => {
    try {
      if (sessionId) {
        sessionStorage.setItem(APP_SESSION_ID_STORAGE_KEY, sessionId);
      }
    } catch (_) {
      // Ignore storage failures.
    }
  }, [sessionId]);

  // Pull verified KYC profile after redirect from video session page.
  useEffect(() => {
    const readProfile = async () => {
      const r = await fetch(`${KYC_API}/get_me`, {
        credentials: "include",
      });
      if (!r.ok) return null;
      return r.json();
    };

    let cancelled = false;
    const pull = async () => {
      try {
        const data = await readProfile();
        if (cancelled || !data?.full_name) return;
        setSessionUserName(data.full_name);
        if (data?.session_id) {
          setSessionId(data.session_id);
        }
        // Cache KYC profile for loan agent
        kycProfileRef.current = {
          full_name: data.full_name,
          email: data.email,
          mobile_number: data.mobile_number,
          aadhaar_masked: data.aadhaar_masked,
          session_id: data.session_id,
        };

        const faceMatch = data?.face_match;
        let faceMatchLabel = null;
        let faceMatchPercentage = null;
        if (
          sessionActive &&
          faceMatch?.available &&
          typeof faceMatch?.percentage === "number"
        ) {
          faceMatchPercentage = faceMatch.percentage;
          faceMatchLabel = faceMatch.is_match ? "Match" : "No match";
        }

        setExtractedData((prev) => ({
          ...prev,
          fullName: prev.fullName || data.full_name,
          dateOfBirth: data?.date_of_birth || prev.dateOfBirth,
          faceMatchLabel: sessionActive
            ? faceMatchLabel || prev.faceMatchLabel || "Pending capture"
            : null,
          faceMatchPercentage,
        }));
      } catch (_) {
        if (cancelled) return;
        setSessionUserName(null);
      }
    };

    pull();
    const timer = setInterval(() => {
      if (sessionActive) {
        pull();
      }
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [sessionActive]);

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

  // ── Submit (Loan Agent) with Streaming ────────────────────────────────────
  const submitText = useCallback(
    async (providedText) => {
      const text = (providedText ?? inputText).trim();
      if (!text || loading || !sessionActive) return;

      setLoading(true);
      setTranscript("");
      setLastUserText(text);
      setAssistantReply("");
      setAssistantProvider("");
      setAvatarVideoUrl("");
      setInputText("");
      appendMessage({ role: "user", text });

      const startedAt = Date.now();

      try {
        // Get complete response as single message
        const res = await fetch("/loan/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            message: text,
            user_id: kycProfileRef.current?.user_id || null,
            kyc_profile: kycProfileRef.current || null,
          }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const responseData = await res.json();
        const responseTime = Date.now() - startedAt;
        const fullReply = responseData.reply || "";

        // Update loan-specific state from metadata
        if (responseData.phase) setLoanPhase(responseData.phase);
        if (responseData.cibl_score) {
          // Extract score from CIBL data object
          const scoreValue = responseData.cibl_score.score || responseData.cibl_score;
          setCiblScore(scoreValue);
        }
        if (responseData.extracted_fields) {
          setLoanExtractedFields(responseData.extracted_fields);
          setExtractedData((prev) => ({
            ...prev,
            monthlyIncome: responseData.extracted_fields.monthly_income
              ? `₹${Number(responseData.extracted_fields.monthly_income).toLocaleString("en-IN")}`
              : prev.monthlyIncome,
            loanPurpose:
              responseData.extracted_fields.loan_purpose || prev.loanPurpose,
          }));
        }
        if (responseData.offer) setCurrentOffer(responseData.offer);

        // Track response time
        setResponseTimes((prev) => {
          const next = [...prev, responseTime];
          return next.length > 20 ? next.slice(-20) : next;
        });

        // Update intent tracking
        handleIntent(responseData.phase || "loan");

        // Add complete message to chat
        appendMessage({
          role: "ai",
          text: fullReply,
          intent: responseData.phase,
          provider: "gemini",
          rt: responseTime,
        });

        // Auto-show modal when reaching final stage
        if (responseData.is_final && responseData.offer && !loanApproved) {
          setShowOfferModal(true);
        }

        // Start TTS immediately (before avatar video, if any)
        await speakReply(fullReply);

        // Try to get avatar video, but don't wait for it
        try {
          const avatarRes = await fetch("/api/avatar/talk", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: fullReply }),
          });
          if (!avatarRes.ok) throw new Error(`HTTP ${avatarRes.status}`);
          const avatarData = await avatarRes.json();
          setAvatarVideoUrl(avatarData.result_url || "");
        } catch (e) {
          console.log("Avatar video unavailable, using TTS only:", e);
          setAvatarVideoUrl("");
        }
      } catch (err) {
        console.error("Loan agent error:", err);
        const fallback =
          "Sorry, I had trouble responding just now. Please try again.";
        setAssistantReply(fallback);
        setAssistantProvider("fallback");
        appendMessage({ role: "ai", text: fallback, provider: "fallback" });
        setAvatarVideoUrl("");
        await speakReply(fallback);
      } finally {
        setLoading(false);
        setAvatarState("idle");
      }
    },
    [
      appendMessage,
      handleIntent,
      inputText,
      loading,
      sessionActive,
      sessionId,
      speakReply,
      loanApproved,
    ],
  );

  // ── Loan Offer Accept ───────────────────────────────────────────────────────
  const handleAcceptOffer = useCallback(async () => {
    // Safety check: only allow approval at appropriate phases
    const validPhases = ["recommendation", "negotiation", "confirmation"];
    if (!currentOffer || loanApproving || !validPhases.includes(loanPhase)) {
      if (!validPhases.includes(loanPhase)) {
        appendMessage({ 
          role: "ai", 
          text: `❌ Cannot approve at this stage (${loanPhase}). Please complete the loan consultation first.`, 
          provider: "system" 
        });
      }
      return;
    }
    setLoanApproving(true);
    try {
      const res = await fetch("/loan/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          user_id: kycProfileRef.current?.user_id || null,
          approved_terms: {
            amount: currentOffer.amount,
            interest_rate: currentOffer.interest_rate,
            tenure_months: currentOffer.tenure_months,
          },
        }),
      });
      
      const result = await res.json();
      
      if (!res.ok) {
        throw new Error(result.detail || `HTTP ${res.status}`);
      }
      
      setLoanApproved(true);
      setShowOfferModal(false);
      setLoanPhase("done");
      const msg = `✅ Offer accepted! Application ID: ${result.application_id || "N/A"}. Our team will reach out within 24 hours for document collection.`;
      appendMessage({ role: "ai", text: msg, intent: "done", provider: "system" });
      setAssistantReply(msg);
      await speakReply("Congratulations! Your loan application has been accepted. We will contact you shortly.");
    } catch (err) {
      console.error("Approve error:", err);
      const errorMsg = err.message || "There was an error processing your acceptance.";
      appendMessage({ 
        role: "ai", 
        text: `❌ Error: ${errorMsg}. Please ensure you've gone through the loan consultation to get a recommended offer.`, 
        provider: "system" 
      });
    } finally {
      setLoanApproving(false);
    }
  }, [currentOffer, loanApproving, sessionId, appendMessage, speakReply]);

  // ── Loan Offer Negotiate ────────────────────────────────────────────────────
  const handleNegotiateOffer = useCallback(() => {
    setShowOfferModal(false);
    submitText("I'd like to negotiate the terms — can we discuss the interest rate or amount?");
  }, [submitText]);

  // ── Toggle session ───────────────────────────────────────────────────────────
  const toggleSession = () => {
    if (sessionActive) {
      synthRef.current?.cancel();
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      setLoanPhase("discovery");
      setCurrentOffer(null);
      setShowOfferModal(false);
      setLoanApproved(false);
      setLoanExtractedFields({});
      setLoanApproving(false);
      kycProfileRef.current = null;
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
      setAssistantProvider("");
      setAvatarVideoUrl("");
      setInputText("");
      setLoading(false);
      setIsSecurityAlertActive(false);
      setSecurityAlertType("none");
      setViolationCount(0);
      setViolationSecondsRemaining(0);
      setMeetingTerminated(false);
      setMeetingEndMessage("");
      setShowDecisionWhy(false);
      setSessionId(createSessionId());
      setExtractedData({
        fullName: null,
        dateOfBirth: null,
        age: null,
        monthlyIncome: null,
        loanPurpose: null,
        faceMatchLabel: null,
        faceMatchPercentage: null,
      });
    } else {
      setExtractedData((prev) => ({
        ...prev,
        faceMatchLabel: "Pending capture",
        faceMatchPercentage: null,
      }));
    }
    setSessionActive((v) => !v);
  };

  const ageApproval = useMemo(() => {
    const estimated = Math.round(ageData?.average_age || 0);
    const dob = extractedData?.dateOfBirth;
    if (!sessionActive || !dob || !estimated) return null;
    const birthYear = Number(String(dob).slice(0, 4));
    if (!birthYear) return null;
    const realAge = currentYear - birthYear;
    const within = Math.abs(estimated - realAge) <= 10;
    return {
      approved: within,
      realAge,
      estimatedAge: estimated,
    };
  }, [ageData, currentYear, extractedData?.dateOfBirth, sessionActive]);

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
              FinServe
            </span>
            {sessionActive && sessionUserName && (
              <span className="kyc-topbar-user">Hi, {sessionUserName}</span>
            )}
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
            sessionActive={sessionActive}
            ageApproval={ageApproval}
            ciblScore={ciblScore}
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
      {/* {decisionReady && (
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
      )} */}

      {/* ── Loan Phase Indicator (when active) ── */}
      {sessionActive && loanPhase && loanPhase !== "discovery" && (
        <div className="kyc-loan-phase-bar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
            <line x1="1" y1="10" x2="23" y2="10" />
          </svg>
          <span>Loan Advisor &mdash; Phase: <strong>{loanPhase}</strong></span>
          {currentOffer && !showOfferModal && ["recommendation", "negotiation", "confirmation"].includes(loanPhase) && (
            <button
              className="kyc-loan-view-offer-btn"
              onClick={() => setShowOfferModal(true)}
            >
              View Offer
            </button>
          )}
        </div>
      )}

      {/* ── Loan Offer Modal ── */}
      {showOfferModal && currentOffer && (
        <LoanOfferModal
          offer={currentOffer}
          onAccept={handleAcceptOffer}
          onNegotiate={handleNegotiateOffer}
          onClose={() => setShowOfferModal(false)}
          loading={loanApproving}
          sessionUserName={sessionUserName}
        />
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
