/**
 * App - root layout for AI Video Onboarding MVP.
 * Wires: webcam -> liveness, assistant replies -> speaking avatar, voice + text -> shared conversation flow.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react'
import WebcamFeed from './components/WebcamFeed.jsx'
import LivenessPanel from './components/LivenessPanel.jsx'
import TalkingAvatar from './components/TalkingAvatar.jsx'
import VoiceChat from './components/VoiceChat.jsx'
import OnboardingProgress from './components/OnboardingProgress.jsx'
import AnalyticsPanel from './components/AnalyticsPanel.jsx'

function createSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return `session-${Date.now()}`
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

  const handleLiveness = useCallback((data) => {
    setLivenessData(data)
    setLivenessSamples((prev) => {
      const next = [...prev, data.liveness_score]
      return next.length > 30 ? next.slice(-30) : next
    })
  }, [])

  const handleIntent = useCallback((intent) => {
    setCurrentIntent(intent)
    setCompletedIntents((prev) => (prev.includes(intent) ? prev : [...prev, intent]))
  }, [])

  const appendMessage = useCallback((message) => {
    setMessages((prev) => {
      const next = [...prev, message]
      setMessageCount(next.length)
      return next
    })
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

    const voices = synth.getVoices()
    const preferred = voices.find(
      (voice) => voice.lang === 'en-US' || voice.name.includes('Google') || voice.name.includes('Samantha')
    )
    if (preferred) utterance.voice = preferred

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

    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = null
    }

    try {
      const res = await fetch('/api/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          voice: 'marin',
          instructions: 'Speak warmly, naturally, and conversationally like a polished human onboarding assistant.',
          response_format: 'wav',
        }),
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const blob = await res.blob()
      if (!blob.size) {
        throw new Error('Empty audio response')
      }

      const audio = audioRef.current || new Audio()
      audioRef.current = audio

      const url = URL.createObjectURL(blob)
      audioUrlRef.current = url

      audio.src = url
      audio.onplay = () => setAvatarState('speaking')
      audio.onended = () => setAvatarState('idle')
      audio.onerror = () => {
        setAvatarState('idle')
        speakReplyFallback(text)
      }

      await audio.play()
    } catch (err) {
      console.warn('Backend TTS unavailable, using browser fallback:', err)
      speakReplyFallback(text)
    }
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

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data = await res.json()
      const responseTime = Date.now() - startedAt

      setResponseTimes((prev) => {
        const next = [...prev, responseTime]
        return next.length > 20 ? next.slice(-20) : next
      })

      setAssistantReply(data.reply)
      setAssistantProvider(data.provider || '')
      handleIntent(data.intent)
      appendMessage({ role: 'ai', text: data.reply, intent: data.intent, rt: responseTime, suggestions: data.suggestions })
      try {
        const avatarRes = await fetch('/api/avatar/talk', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: data.reply }),
        })
        if (!avatarRes.ok) {
          throw new Error(`HTTP ${avatarRes.status}`)
        }
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
      appendMessage({ role: 'ai', text: fallback })
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
      setMessages([])
      setLoading(false)
      setSessionId(createSessionId())
    }
    setSessionActive((value) => !value)
  }

  const livenessScore = livenessData ? Math.round(livenessData.liveness_score * 100) : 0

  return (
    <div className="min-h-screen bg-ink font-body text-gray-200 flex flex-col">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute top-[-20%] left-[-10%] w-[600px] h-[600px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(110,231,183,0.055) 0%, transparent 65%)' }}
        />
        <div
          className="absolute bottom-[-15%] right-[-5%] w-[500px] h-[500px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(129,140,248,0.065) 0%, transparent 65%)' }}
        />
        <div
          className="absolute top-[40%] left-[50%] w-[300px] h-[300px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(251,191,36,0.025) 0%, transparent 65%)' }}
        />
      </div>

      <header className="relative z-10 flex items-center justify-between px-6 lg:px-8 py-4 border-b border-border/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-accent2 flex items-center justify-center flex-shrink-0">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0a0f" strokeWidth="2.5">
              <circle cx="12" cy="8" r="4" />
              <path d="M20 21a8 8 0 1 0-16 0" />
            </svg>
          </div>
          <div>
            <span className="font-display font-bold text-lg tracking-tight leading-none block">
              on<span className="text-gradient">board</span>.ai
            </span>
            <span className="text-[10px] font-mono text-muted leading-none">AI-powered onboarding</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className={`hidden sm:flex items-center gap-2 text-xs font-mono px-3 py-1.5 rounded-full border transition-all ${
              sessionActive ? 'border-accent/40 text-accent bg-accent/10' : 'border-border text-muted bg-surface'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${sessionActive ? 'bg-accent animate-pulse' : 'bg-muted'}`} />
            {sessionActive ? 'Session active' : 'Ready'}
          </div>
          <button
            onClick={toggleSession}
            className="text-xs font-display font-semibold px-4 py-1.5 rounded-full transition-all cursor-pointer"
            style={{
              background: sessionActive ? 'transparent' : 'linear-gradient(135deg, #6ee7b7, #818cf8)',
              color: sessionActive ? '#f87171' : '#0a0a0f',
              border: sessionActive ? '1px solid rgba(248,113,113,0.6)' : 'none',
            }}
          >
            {sessionActive ? 'End Session' : 'Start Session'}
          </button>
        </div>
      </header>

      <main className="relative z-10 flex-1 grid grid-cols-1 lg:grid-cols-3 gap-5 p-5 max-w-7xl mx-auto w-full">
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-muted uppercase tracking-widest">Camera Feed</span>
            <div className="flex-1 h-px bg-border/50" />
            <span className="text-[10px] font-mono text-muted/50">2s analysis interval</span>
          </div>

          <WebcamFeed
            onLivenessUpdate={handleLiveness}
            onAgeUpdate={setAgeData}
            onAgeError={setAgeError}
            active={sessionActive}
            sessionId={sessionId}
          />

          <div className="card-glass rounded-xl px-5 py-3 flex items-center gap-4">
            <span className="text-xs font-mono text-muted whitespace-nowrap w-24">Liveness</span>
            <div className="flex-1 h-1.5 bg-border rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${livenessScore}%`,
                  background:
                    livenessScore >= 70
                      ? 'linear-gradient(90deg, #34d399, #6ee7b7)'
                      : livenessScore >= 40
                      ? 'linear-gradient(90deg, #f59e0b, #fbbf24)'
                      : 'linear-gradient(90deg, #ef4444, #f87171)',
                }}
              />
            </div>
            <span
              className="text-sm font-display font-bold w-8 text-right"
              style={{ color: livenessScore >= 70 ? '#6ee7b7' : livenessScore >= 40 ? '#fbbf24' : '#f87171' }}
            >
              {livenessScore}
            </span>
          </div>

          <AnalyticsPanel
            sessionActive={sessionActive}
            messageCount={messageCount}
            responseTimes={responseTimes}
            livenessSamples={livenessSamples}
          />
        </div>

        <div className="flex flex-col gap-4">
          <TalkingAvatar
            state={avatarState}
            transcript={transcript}
            lastUserText={lastUserText}
            assistantReply={assistantReply}
            assistantProvider={assistantProvider}
            avatarVideoUrl={avatarVideoUrl}
            sessionId={sessionId}
            inputText={inputText}
            loading={loading}
            sessionActive={sessionActive}
            onInputChange={setInputText}
            onSubmitText={() => submitText()}
            onVideoPlay={() => setAvatarState('speaking')}
            onVideoEnd={() => setAvatarState('idle')}
            onVideoError={() => setAvatarVideoUrl('')}
          />

          <OnboardingProgress
            currentIntent={currentIntent}
            completedIntents={completedIntents}
          />

          <LivenessPanel data={livenessData} ageData={ageData} ageError={ageError} />

          <VoiceChat
            messages={messages}
            loading={loading}
            sessionActive={sessionActive}
            onStateChange={setAvatarState}
            onSubmitText={submitText}
            onTranscriptChange={setTranscript}
          />
        </div>
      </main>

      <footer className="relative z-10 text-center py-3 border-t border-border/30">
        <p className="text-[10px] font-mono text-muted/40">
          AI Video Onboarding MVP · MediaPipe · Web Speech API · FastAPI
        </p>
      </footer>
    </div>
  )
}
