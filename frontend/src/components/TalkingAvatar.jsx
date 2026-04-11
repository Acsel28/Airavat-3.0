import React, { useEffect, useState } from 'react'

function SpeechBars({ active }) {
  const bars = [16, 28, 20, 34, 24, 30, 18]

  return (
    <div className="flex items-end justify-center gap-1 h-10">
      {bars.map((height, index) => (
        <span
          key={index}
          className={`w-1.5 rounded-full transition-all duration-150 ${
            active ? 'bg-accent opacity-100' : 'bg-border opacity-60'
          }`}
          style={{
            height: active ? height : 8,
            animation: active ? `pulse ${0.45 + index * 0.07}s ease-in-out infinite` : 'none',
          }}
        />
      ))}
    </div>
  )
}

const MOUTH_SHAPES = [
  { width: 18, height: 8, radius: 8 },
  { width: 26, height: 14, radius: 12 },
  { width: 14, height: 18, radius: 10 },
  { width: 30, height: 10, radius: 8 },
]

export default function TalkingAvatar({
  state = 'idle',
  transcript = '',
  lastUserText = '',
  assistantReply = '',
  assistantProvider = '',
  avatarVideoUrl = '',
  sessionId = '',
  inputText = '',
  loading = false,
  sessionActive = false,
  onInputChange,
  onSubmitText,
  onVideoPlay,
  onVideoEnd,
  onVideoError,
}) {
  const [mouthIndex, setMouthIndex] = useState(0)
  const [blink, setBlink] = useState(false)
  const [videoReady, setVideoReady] = useState(false)

  const isSpeaking = state === 'speaking'
  const isListening = state === 'listening'
  const coreGlow = isSpeaking ? '#7c9cff' : isListening ? '#6ee7b7' : '#7dd3fc'

  useEffect(() => {
    if (!isSpeaking) {
      setMouthIndex(0)
      return
    }

    const timer = window.setInterval(() => {
      setMouthIndex((value) => (value + 1) % MOUTH_SHAPES.length)
    }, 110)

    return () => window.clearInterval(timer)
  }, [isSpeaking])

  useEffect(() => {
    const timer = window.setInterval(() => {
      setBlink(true)
      window.setTimeout(() => setBlink(false), 140)
    }, 3200)

    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    setVideoReady(false)
  }, [avatarVideoUrl])

  const mouth = isSpeaking ? MOUTH_SHAPES[mouthIndex] : { width: 28, height: 6, radius: 6 }

  return (
    <div className="card-glass rounded-2xl p-5 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[10px] font-mono text-muted uppercase tracking-[0.28em]">AI Avatar</p>
          <h3 className="text-lg font-display font-semibold text-gray-100 mt-1">Live Conversation</h3>
        </div>
        <div
          className="px-3 py-1 rounded-full border text-[10px] font-mono transition-all duration-300"
          style={{
            color: coreGlow,
            borderColor: `${coreGlow}55`,
            background: `${coreGlow}12`,
            boxShadow: isSpeaking || isListening ? `0 0 18px ${coreGlow}33` : 'none',
          }}
        >
          {isSpeaking ? 'Speaking...' : isListening ? 'Listening...' : loading ? 'Thinking...' : 'Ready'}
        </div>
      </div>

      <div className="relative flex flex-col items-center justify-center py-2">
        <div
          className="absolute h-72 w-72 rounded-full blur-3xl transition-all duration-500"
          style={{
            background: `radial-gradient(circle, ${coreGlow}2d 0%, transparent 72%)`,
            transform: isSpeaking || isListening ? 'scale(1.06)' : 'scale(0.94)',
            opacity: isSpeaking || isListening ? 1 : 0.68,
          }}
        />

        <div className={`relative transition-all duration-300 ${isSpeaking ? 'scale-[1.03] -translate-y-1' : 'scale-100'}`}>
          {avatarVideoUrl && videoReady ? (
            <video
              key={avatarVideoUrl}
              src={avatarVideoUrl}
              autoPlay
              playsInline
              controls={false}
              className="relative z-10 w-[240px] h-[260px] object-cover rounded-[2rem] border border-white/10"
              onPlay={() => onVideoPlay?.()}
              onEnded={() => onVideoEnd?.()}
              onError={() => {
                setVideoReady(false)
                onVideoError?.()
              }}
            />
          ) : (
          <svg width={240} height={260} viewBox="0 0 240 260" className="relative z-10">
            <defs>
              <linearGradient id="avatarBg" x1="0%" x2="100%" y1="0%" y2="100%">
                <stop offset="0%" stopColor="#111827" />
                <stop offset="100%" stopColor="#1f2937" />
              </linearGradient>
              <radialGradient id="skinTone" cx="45%" cy="35%">
                <stop offset="0%" stopColor="#f6d5bf" />
                <stop offset="100%" stopColor="#d8a07d" />
              </radialGradient>
              <linearGradient id="hairTone" x1="0%" x2="100%">
                <stop offset="0%" stopColor="#25160f" />
                <stop offset="100%" stopColor="#4a2c1f" />
              </linearGradient>
              <linearGradient id="shirtTone" x1="0%" x2="100%">
                <stop offset="0%" stopColor="#1d4ed8" />
                <stop offset="100%" stopColor="#4338ca" />
              </linearGradient>
              <filter id="softGlow">
                <feGaussianBlur stdDeviation="10" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <circle cx="120" cy="124" r="96" fill="url(#avatarBg)" opacity="0.88" />

            <ellipse cx="120" cy="232" rx="66" ry="28" fill="url(#shirtTone)" opacity="0.98" />
            <rect x="80" y="190" width="80" height="52" rx="26" fill="url(#shirtTone)" />
            <rect x="106" y="168" width="28" height="34" rx="12" fill="url(#skinTone)" />

            <path
              d="M66 106 C66 54, 94 34, 120 34 C146 34, 174 54, 174 106 L174 134 C174 174, 148 198, 120 198 C92 198, 66 174, 66 134 Z"
              fill="url(#skinTone)"
              filter="url(#softGlow)"
            />

            <path
              d="M60 102 C56 56, 90 18, 122 18 C156 18, 188 48, 182 112 C174 94, 162 84, 148 78 C134 72, 102 70, 82 84 C72 90, 65 96, 60 102 Z"
              fill="url(#hairTone)"
            />
            <path
              d="M72 64 C78 44, 98 28, 122 28 C148 28, 166 44, 172 72 C160 58, 142 50, 120 50 C100 50, 84 56, 72 64 Z"
              fill="#120c08"
              opacity="0.55"
            />

            <ellipse cx="69" cy="126" rx="8" ry="16" fill="#d39a78" />
            <ellipse cx="171" cy="126" rx="8" ry="16" fill="#d39a78" />

            <path d="M87 94 Q102 84 115 92" stroke="#2a150f" strokeWidth="5" fill="none" strokeLinecap="round" />
            <path d="M125 92 Q138 84 153 94" stroke="#2a150f" strokeWidth="5" fill="none" strokeLinecap="round" />

            <ellipse cx="99" cy="114" rx="11" ry={blink ? 1.7 : 7.4} fill="#111827" />
            <ellipse cx="141" cy="114" rx="11" ry={blink ? 1.7 : 7.4} fill="#111827" />
            {!blink && (
              <>
                <circle cx="103" cy="111" r="2.6" fill="#fff" opacity="0.9" />
                <circle cx="145" cy="111" r="2.6" fill="#fff" opacity="0.9" />
              </>
            )}

            <path d="M120 114 C114 128, 113 140, 120 145 C127 140, 126 128, 120 114 Z" fill="#bf8b69" opacity="0.92" />
            <path d="M98 154 Q120 166 142 154" stroke="#b96d74" strokeWidth="3" fill="none" opacity="0.4" />

            {isSpeaking ? (
              <rect
                x={120 - mouth.width / 2}
                y={156 - mouth.height / 2}
                width={mouth.width}
                height={mouth.height}
                rx={mouth.radius}
                fill="#3b1111"
              />
            ) : (
              <path
                d={isListening ? 'M102 156 Q120 172 138 156' : 'M100 154 Q120 165 140 154'}
                stroke="#6b1f2a"
                strokeWidth="4.5"
                fill="none"
                strokeLinecap="round"
              />
            )}

            <path
              d="M72 182 C86 196, 102 202, 120 202 C138 202, 154 196, 168 182"
              stroke={coreGlow}
              strokeWidth="2"
              fill="none"
              opacity={isSpeaking || isListening ? 0.8 : 0.28}
            />
          </svg>
          )}

          {avatarVideoUrl && !videoReady && (
            <video
              key={`${avatarVideoUrl}-preload`}
              src={avatarVideoUrl}
              autoPlay
              playsInline
              controls={false}
              className="absolute inset-0 w-[240px] h-[260px] object-cover rounded-[2rem] opacity-0 pointer-events-none"
              onLoadedData={() => setVideoReady(true)}
              onError={() => {
                setVideoReady(false)
                onVideoError?.()
              }}
            />
          )}

          <div
            className="absolute inset-0 rounded-[42%] border transition-all duration-300"
            style={{
              borderColor: `${coreGlow}2b`,
              boxShadow: isSpeaking || isListening ? `0 0 32px ${coreGlow}22` : 'none',
            }}
          />
        </div>

        <SpeechBars active={isSpeaking} />
      </div>

      <div className="rounded-2xl border border-border/70 bg-black/10 p-3 space-y-3">
        <div>
          <p className="text-[10px] font-mono text-muted uppercase tracking-[0.22em] mb-1">You Said</p>
          <p className="text-sm text-gray-200 min-h-5">
            {transcript || lastUserText || 'Type below or use the mic to talk to the assistant.'}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-mono text-muted uppercase tracking-[0.22em] mb-1">Assistant Reply</p>
          {assistantProvider && (
            <p className="text-[10px] font-mono text-accent/80 mb-1 uppercase tracking-[0.18em]">
              Provider: {assistantProvider}
            </p>
          )}
          <p className="text-sm text-gray-200 min-h-10">
            {assistantReply || 'The assistant will respond here and speak the reply out loud.'}
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-border/70 bg-black/10 p-3">
        <label htmlFor="avatar-text-input" className="block text-[11px] font-mono text-muted uppercase tracking-[0.22em] mb-2">
          Tell The Assistant What To Say
        </label>
        <div className="flex flex-col gap-3">
          <input
            id="avatar-text-input"
            type="text"
            value={inputText}
            onChange={(e) => onInputChange?.(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onSubmitText?.()
            }}
            placeholder="Say hello, ask a question, or start onboarding..."
            disabled={!sessionActive || loading || isSpeaking}
            className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-sm text-gray-100 outline-none transition-all duration-200 placeholder:text-muted/70 focus:border-accent/60 focus:ring-2 focus:ring-accent/20 disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => onSubmitText?.()}
            disabled={!sessionActive || !inputText.trim() || loading || isSpeaking}
            className="inline-flex items-center justify-center rounded-xl px-4 py-3 text-sm font-display font-semibold transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              background: 'linear-gradient(135deg, #6ee7b7 0%, #818cf8 100%)',
              color: '#0a0a0f',
              boxShadow: '0 14px 30px rgba(129,140,248,0.16)',
            }}
          >
            {isSpeaking ? 'Speaking...' : loading ? 'Thinking...' : 'Send And Speak'}
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between text-[11px] font-mono text-muted">
        <span>{sessionId ? `Session ${sessionId.slice(0, 8)}` : 'Session not started'}</span>
        <span className={isSpeaking || isListening ? 'text-accent' : ''}>
          {!sessionActive ? 'Start session first' : isSpeaking ? 'Voice active' : isListening ? 'Capturing voice' : 'Standby'}
        </span>
      </div>
    </div>
  )
}
