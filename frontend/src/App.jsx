import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import VideoPanel from './components/VideoPanel.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import TrustPanel from './components/TrustPanel.jsx'
import ProgressBar from './components/ProgressBar.jsx'

function createSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `session-${Date.now()}`
}

function mapSecurityMessage(alertType) {
  switch (alertType) {
    case 'multiple_faces':
      return 'Multiple people detected. Please ensure only you are in the frame.'
    case 'no_face':
      return 'We can’t see you. Please face the camera.'
    case 'different_person':
      return 'Face mismatch detected. Please verify identity.'
    case 'meeting_ended':
      return 'Session ended due to repeated violations.'
    default:
      return ''
  }
}

function deriveStage({ sessionActive, data, messages, completedIntents, meetingTerminated }) {
  if (!sessionActive && messages.length === 0) return 'intro'
  if (meetingTerminated) return 'verification'
  if (!data?.is_verified || !data?.face_detected) return 'verification'
  if (completedIntents.includes('done') || messages.length >= 6) return 'decision'
  return 'questioning'
}

function deriveDecision({ livenessScore, violationCount, meetingTerminated, faceVerified }) {
  const approved = !meetingTerminated && faceVerified && livenessScore >= 65 && violationCount < 2
  return {
    approved,
    amount: approved ? 280000 : 120000,
    emi: approved ? 8240 : 5410,
    tenure: approved ? 36 : 24,
  }
}

export default function App() {
  const [livenessData, setLivenessData] = useState(null)
  const [ageData, setAgeData] = useState(null)
  const [ageError, setAgeError] = useState('')
  const [avatarState, setAvatarState] = useState('idle')
  const [transcript, setTranscript] = useState('')
  const [lastUserText, setLastUserText] = useState('')
  const [assistantReply, setAssistantReply] = useState('')
  const [assistantProvider, setAssistantProvider] = useState('')
  const [avatarVideoUrl, setAvatarVideoUrl] = useState('')
  const [inputText, setInputText] = useState('')
  const [sessionId, setSessionId] = useState(createSessionId)
  const [sessionActive, setSessionActive] = useState(false)
  const [currentIntent, setCurrentIntent] = useState('greeting')
  const [completedIntents, setCompletedIntents] = useState([])
  const [messageCount, setMessageCount] = useState(0)
  const [responseTimes, setResponseTimes] = useState([])
  const [livenessSamples, setLivenessSamples] = useState([])
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [isSecurityAlertActive, setIsSecurityAlertActive] = useState(false)
  const [securityAlertType, setSecurityAlertType] = useState('none')
  const [violationCount, setViolationCount] = useState(0)
  const [violationSecondsRemaining, setViolationSecondsRemaining] = useState(0)
  const [meetingTerminated, setMeetingTerminated] = useState(false)
  const [meetingEndMessage, setMeetingEndMessage] = useState('')
  const [showDecisionWhy, setShowDecisionWhy] = useState(false)

  const synthRef = useRef(typeof window !== 'undefined' ? window.speechSynthesis : null)
  const audioRef = useRef(null)
  const audioUrlRef = useRef(null)

  useEffect(() => {
    return () => {
      synthRef.current?.cancel()
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.src = ''
      }
      if (audioUrlRef.current) {
        URL.revokeObjectURL(audioUrlRef.current)
      }
    }
  }, [])

  const livenessScore = livenessData ? Math.round((livenessData.liveness_score || 0) * 100) : 0
  const securityMessage = mapSecurityMessage(securityAlertType)

  const fraudScore = useMemo(() => {
    const penalty = (violationCount * 18) + (livenessData?.security_alert && livenessData.security_alert !== 'none' ? 22 : 0)
    return Math.min(100, penalty)
  }, [livenessData, violationCount])

  const riskScore = useMemo(() => {
    const base = 100 - livenessScore
    return Math.min(100, Math.max(0, Math.round((base * 0.55) + fraudScore * 0.45)))
  }, [fraudScore, livenessScore])

  const stage = useMemo(
    () =>
      deriveStage({
        sessionActive,
        data: livenessData,
        messages,
        completedIntents,
        meetingTerminated,
      }),
    [sessionActive, livenessData, messages, completedIntents, meetingTerminated]
  )

  const progressStep = stage === 'intro'
    ? 'identity'
    : stage === 'verification'
    ? 'verification'
    : stage === 'questioning'
    ? 'financial'
    : 'decision'

  const decision = useMemo(
    () =>
      deriveDecision({
        livenessScore,
        violationCount,
        meetingTerminated,
        faceVerified: Boolean(livenessData?.is_verified),
      }),
    [livenessData, livenessScore, meetingTerminated, violationCount]
  )

  const decisionReady = stage === 'decision'

  const appendMessage = useCallback((message) => {
    setMessages((prev) => {
      const next = [...prev, { ...message, timestamp: Date.now() }]
      setMessageCount(next.length)
      return next
    })
  }, [])

  const handleIntent = useCallback((intent) => {
    setCurrentIntent(intent)
    setCompletedIntents((prev) => (prev.includes(intent) ? prev : [...prev, intent]))
  }, [])

  const handleLiveness = useCallback((data) => {
    setLivenessData(data)
    setLivenessSamples((prev) => {
      const next = [...prev, data.liveness_score]
      return next.length > 30 ? next.slice(-30) : next
    })

    const alert = data?.security_alert && data.security_alert !== 'none'
    setIsSecurityAlertActive(Boolean(alert))
    setSecurityAlertType(data?.security_alert || 'none')
    setViolationCount(data?.violation_count || 0)
    setViolationSecondsRemaining(data?.violation_seconds_remaining || 0)

    if (data?.meeting_terminated) {
      setMeetingTerminated(true)
      setMeetingEndMessage(data?.meeting_end_message || 'Meeting ended due to multiple identity violations.')
      setSessionActive(false)
      setAvatarState('idle')
    }
  }, [])

  const handleSecurityState = useCallback((data) => {
    const alert = data?.security_alert && data.security_alert !== 'none'
    setIsSecurityAlertActive(Boolean(alert))
    setSecurityAlertType(data?.security_alert || 'none')
    setViolationCount(data?.violation_count || 0)
    setViolationSecondsRemaining(data?.violation_seconds_remaining || 0)
  }, [])

  const speakReplyFallback = useCallback((text) => {
    const synth = synthRef.current
    if (!synth || !text) {
      setAvatarState('idle')
      return
    }

    synth.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 0.96
    utterance.pitch = 1.02
    utterance.volume = 1
    utterance.onstart = () => setAvatarState('speaking')
    utterance.onend = () => setAvatarState('idle')
    utterance.onerror = () => setAvatarState('idle')
    synth.speak(utterance)
  }, [])

  const speakReply = useCallback(async (text) => {
    if (!text) {
      setAvatarState('idle')
      return
    }

    // Gemini handles text responses; use browser speech fallback for audio when D-ID is unavailable.
    speakReplyFallback(text)
  }, [speakReplyFallback])

  const submitText = useCallback(async (providedText) => {
    const text = (providedText ?? inputText).trim()
    if (!text || loading || !sessionActive) return

    setLoading(true)
    setTranscript('')
    setLastUserText(text)
    setAssistantReply('')
    setAssistantProvider('')
    setAvatarVideoUrl('')
    setInputText('')
    appendMessage({ role: 'user', text })

    const startedAt = Date.now()

    try {
      const res = await fetch('/process-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, session_id: sessionId }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const data = await res.json()
      const responseTime = Date.now() - startedAt

      setResponseTimes((prev) => {
        const next = [...prev, responseTime]
        return next.length > 20 ? next.slice(-20) : next
      })

      setAssistantReply(data.reply)
      setAssistantProvider(data.provider || '')
      handleIntent(data.intent)
      appendMessage({
        role: 'ai',
        text: data.reply,
        intent: data.intent,
        provider: data.provider,
        rt: responseTime,
        suggestions: data.suggestions,
      })

      try {
        const avatarRes = await fetch('/api/avatar/talk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: data.reply }),
        })
        if (!avatarRes.ok) throw new Error(`HTTP ${avatarRes.status}`)
        const avatarData = await avatarRes.json()
        setAvatarVideoUrl(avatarData.result_url || '')
      } catch (avatarErr) {
        console.warn('D-ID talk unavailable, using audio fallback:', avatarErr)
        setAvatarVideoUrl('')
        await speakReply(data.reply)
      }
    } catch (err) {
      console.error('Assistant error:', err)
      const fallback = 'Sorry, I had trouble responding just now. Please try again.'
      setAssistantReply(fallback)
      setAssistantProvider('fallback')
      appendMessage({ role: 'ai', text: fallback, provider: 'fallback' })
      setAvatarVideoUrl('')
      await speakReply(fallback)
    } finally {
      setLoading(false)
    }
  }, [appendMessage, handleIntent, inputText, loading, sessionActive, sessionId, speakReply])

  const toggleSession = () => {
    if (sessionActive) {
      synthRef.current?.cancel()
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.currentTime = 0
      }
      setCurrentIntent('greeting')
      setCompletedIntents([])
      setMessageCount(0)
      setResponseTimes([])
      setLivenessSamples([])
      setMessages([])
      setLivenessData(null)
      setAgeData(null)
      setAgeError('')
      setAvatarState('idle')
      setTranscript('')
      setLastUserText('')
      setAssistantReply('')
      setAssistantProvider('')
      setAvatarVideoUrl('')
      setInputText('')
      setLoading(false)
      setIsSecurityAlertActive(false)
      setSecurityAlertType('none')
      setViolationCount(0)
      setViolationSecondsRemaining(0)
      setMeetingTerminated(false)
      setMeetingEndMessage('')
      setShowDecisionWhy(false)
      setSessionId(createSessionId())
    }
    setSessionActive((value) => !value)
  }

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_top_left,_rgba(99,102,241,0.16),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(168,85,247,0.16),_transparent_30%)]" />

      <div className="relative z-10 mx-auto flex min-h-screen max-w-[1600px] flex-col px-5 py-5 lg:px-8">
        <header className="mb-5 flex flex-col gap-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-[0.32em] text-slate-500">AI Onboarding</p>
              <h1 className="text-2xl font-semibold text-white lg:text-3xl">Loan Verification Intelligence Hub</h1>
            </div>
            <button
              onClick={toggleSession}
              className={`rounded-full px-5 py-3 text-sm font-semibold transition ${
                sessionActive
                  ? 'border border-rose-400/30 bg-rose-400/10 text-rose-100 hover:bg-rose-400/15'
                  : 'bg-gradient-to-r from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/20 hover:scale-[1.02]'
              }`}
            >
              {sessionActive ? 'End Session' : 'Start Session'}
            </button>
          </div>

          <ProgressBar current={progressStep} />

          {isSecurityAlertActive && !meetingTerminated && (
            <div className="rounded-2xl border border-amber-400/30 bg-amber-400/10 px-5 py-4 text-sm text-amber-100 shadow-lg">
              <p className="font-semibold">Attention needed</p>
              <p className="mt-1">{securityMessage}</p>
              <p className="mt-2 text-xs font-mono uppercase tracking-[0.22em] text-amber-200/70">
                Violations {violationCount}/3 · timer {violationSecondsRemaining}s
              </p>
            </div>
          )}
        </header>

        <main className="grid flex-1 grid-cols-1 gap-5 xl:grid-cols-[1.05fr_1.25fr_0.95fr]">
          <VideoPanel
            sessionActive={sessionActive}
            sessionId={sessionId}
            avatarState={avatarState}
            avatarVideoUrl={avatarVideoUrl}
            assistantReply={assistantReply}
            onLivenessUpdate={handleLiveness}
            onSecurityState={handleSecurityState}
            onAgeUpdate={setAgeData}
            onAgeError={setAgeError}
          />

          <ChatPanel
            messages={messages}
            loading={loading}
            sessionActive={sessionActive}
            inputText={inputText}
            onInputChange={setInputText}
            onSubmitText={submitText}
            onStateChange={setAvatarState}
            onTranscriptChange={setTranscript}
          />

          <TrustPanel
            data={livenessData}
            ageData={ageData}
            ageError={ageError}
            riskScore={riskScore}
            fraudScore={fraudScore}
            violationCount={violationCount}
            securityMessage={securityMessage}
          />
        </main>

        {decisionReady && (
          <div className="pointer-events-none fixed inset-0 z-40 flex items-center justify-center bg-slate-950/75 p-6 backdrop-blur-sm">
            <div className="pointer-events-auto w-full max-w-3xl rounded-[2rem] border border-white/10 bg-slate-900/95 p-8 shadow-2xl">
              <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-[0.32em] text-slate-500">Decision Ready</p>
                  <h2 className={`mt-2 text-3xl font-semibold ${decision.approved ? 'text-emerald-300' : 'text-amber-300'}`}>
                    {decision.approved ? 'Approved with conditions' : 'Further review recommended'}
                  </h2>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-slate-300">
                    {decision.approved
                      ? 'The onboarding signals are strong enough to present a preliminary offer. Review the terms below and continue.'
                      : 'We need a little more verification confidence before locking the final terms. You can still review the provisional structure.'}
                  </p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-950/50 px-4 py-3 text-right">
                  <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-slate-500">Current Stage</p>
                  <p className="mt-1 text-sm font-semibold text-white capitalize">{stage}</p>
                </div>
              </div>

              <div className="mt-8 grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-slate-500">Loan Amount</p>
                  <p className="mt-2 text-3xl font-semibold text-white">₹{decision.amount.toLocaleString('en-IN')}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-slate-500">Estimated EMI</p>
                  <p className="mt-2 text-3xl font-semibold text-white">₹{decision.emi.toLocaleString('en-IN')}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
                  <p className="text-[10px] font-mono uppercase tracking-[0.24em] text-slate-500">Tenure</p>
                  <p className="mt-2 text-3xl font-semibold text-white">{decision.tenure} months</p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <button className="rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 px-5 py-3 text-sm font-semibold text-white transition hover:scale-[1.02]">
                  Accept Offer
                </button>
                <button className="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-white transition hover:border-violet-400/40 hover:bg-violet-500/10">
                  Negotiate
                </button>
                <button
                  onClick={() => setShowDecisionWhy((value) => !value)}
                  className="rounded-full border border-indigo-400/30 bg-indigo-500/10 px-5 py-3 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/15"
                >
                  Why this decision?
                </button>
              </div>

              {showDecisionWhy && (
                <div className="mt-6 grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">Income Verification</p>
                    <p className="mt-2 text-sm text-slate-200">Question flow completed with stable session confidence and response consistency.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">Credit Score Proxy</p>
                    <p className="mt-2 text-sm text-slate-200">Financial discussion stage reached with no critical conversation blockers.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">Fraud Signals</p>
                    <p className="mt-2 text-sm text-slate-200">Risk score {riskScore}% with {violationCount} recorded violation events.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-slate-950/45 p-4">
                    <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">Identity Match</p>
                    <p className="mt-2 text-sm text-slate-200">
                      {livenessData?.is_verified ? 'Verified against enrolled session face.' : 'Identity confidence still needs more signal.'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {meetingTerminated && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 p-6 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-[2rem] border border-rose-400/30 bg-rose-500/10 p-8 text-center shadow-2xl">
              <p className="text-[10px] font-mono uppercase tracking-[0.3em] text-rose-200/70">Session Alert</p>
              <h2 className="mt-3 text-3xl font-semibold text-rose-200">Session ended due to repeated violations.</h2>
              <p className="mt-3 text-sm leading-6 text-rose-100/90">
                {meetingEndMessage || 'Session ended due to repeated violations.'}
              </p>
              <button
                onClick={() => {
                  setMeetingTerminated(false)
                  setIsSecurityAlertActive(false)
                }}
                className="mt-6 rounded-full border border-white/10 bg-white/10 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/15"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
