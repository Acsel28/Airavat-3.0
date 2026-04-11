/**
 * VoiceChat - microphone input via Web Speech API.
 * Captures speech, shows the conversation log, and forwards text to the shared assistant pipeline.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition

export default function VoiceChat({
  messages,
  loading,
  sessionActive,
  onStateChange,
  onSubmitText,
  onTranscriptChange,
}) {
  const [listening, setListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [supported, setSupported] = useState(true)

  const recognitionRef = useRef(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    if (!SpeechRecognition) setSupported(false)
  }, [])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  useEffect(() => {
    const onKey = (e) => {
      if (e.code === 'Space' && e.target === document.body && sessionActive) {
        e.preventDefault()
        if (listening) stopListening()
        else startListening()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [listening, sessionActive]) // eslint-disable-line

  const startListening = useCallback(() => {
    if (!SpeechRecognition || listening || !sessionActive || loading) return

    const recognition = new SpeechRecognition()
    recognitionRef.current = recognition
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = 'en-US'

    recognition.onstart = () => {
      setListening(true)
      setTranscript('')
      onTranscriptChange?.('')
      onStateChange?.('listening')
    }

    recognition.onresult = (e) => {
      let interim = ''
      let final = ''

      for (let i = e.resultIndex; i < e.results.length; i++) {
        const value = e.results[i][0].transcript
        if (e.results[i].isFinal) final += value
        else interim += value
      }

      const nextTranscript = final || interim
      setTranscript(nextTranscript)
      onTranscriptChange?.(nextTranscript)

      if (final.trim()) {
        recognition.stop()
        onStateChange?.('listening')
        onSubmitText?.(final.trim())
      }
    }

    recognition.onerror = () => {
      setListening(false)
      setTranscript('')
      onTranscriptChange?.('')
      onStateChange?.('idle')
    }

    recognition.onend = () => {
      setListening(false)
      setTranscript('')
      onTranscriptChange?.('')
      // keep avatar state until a reply is received so it remains visible
    }

    recognition.start()
  }, [listening, loading, onStateChange, onSubmitText, onTranscriptChange, sessionActive])

  const stopListening = () => recognitionRef.current?.stop()

  if (!supported) {
    return (
      <div className="card-glass rounded-2xl p-5 text-center text-sm text-muted">
        Web Speech API not supported. Try Chrome or Edge.
      </div>
    )
  }

  return (
    <div className="card-glass rounded-2xl flex flex-col" style={{ minHeight: 340 }}>
      <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-border/40">
        <h3 className="text-sm font-display font-semibold text-gray-300 uppercase tracking-widest">Conversation</h3>
        <div className="flex items-center gap-3">
          {loading && (
            <div className="flex items-center gap-1.5 text-xs text-accent2 font-mono">
              <div className="w-3 h-3 rounded-full border border-accent2 border-t-transparent animate-spin" />
              thinking...
            </div>
          )}
          <span className="text-[10px] font-mono text-muted/50 hidden sm:block">SPACE to mic</span>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 flex flex-col gap-3" style={{ maxHeight: 220 }}>
        {messages.length === 0 && (
          <div className="text-center text-xs text-muted mt-6 font-body italic">
            Start a session, type a message above, or hold the mic button to speak.
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-accent2/20 text-gray-200 border border-accent2/20'
                  : 'bg-accent/10 text-gray-200 border border-accent/20'
              }`}
            >
              {m.role === 'ai' && (
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[9px] font-mono text-accent uppercase">AI · {m.intent || 'reply'}</span>
                  {m.rt ? <span className="text-[9px] font-mono text-muted">{m.rt}ms</span> : null}
                </div>
              )}
              {m.text}
              {m.suggestions && m.suggestions.length > 0 && (
                <div className="mt-2 text-xs text-muted">
                  <div className="font-mono text-[10px] text-accent mb-1">Try asking:</div>
                  <ul className="list-disc list-inside text-[11px]">
                    {m.suggestions.map((s, idx) => (
                      <li key={idx}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {transcript && (
        <div className="mx-4 mb-2 px-3 py-1.5 rounded-lg bg-accent2/10 border border-accent2/20">
          <p className="text-xs text-accent2 italic">{transcript}...</p>
        </div>
      )}

      <div className="px-5 pb-5 pt-3 flex items-center justify-center gap-4">
        <button
          onMouseDown={startListening}
          onMouseUp={stopListening}
          onTouchStart={startListening}
          onTouchEnd={stopListening}
          disabled={loading || !sessionActive}
          className={`relative flex items-center justify-center rounded-full transition-all duration-200 cursor-pointer ${
            listening
              ? 'w-16 h-16 glow-accent bg-accent/20 border-2 border-accent'
              : 'w-14 h-14 bg-card border-2 border-border hover:border-accent/50 hover:bg-accent/10'
          } ${loading || !sessionActive ? 'opacity-40 cursor-not-allowed' : ''}`}
        >
          {listening && <span className="absolute inset-0 rounded-full animate-ping bg-accent/30" />}
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke={listening ? '#6ee7b7' : '#9ca3af'}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
        </button>
        <p className="text-xs text-muted font-body">
          {!sessionActive ? 'Start a session to enable mic' : listening ? 'Listening... release to send' : 'Hold to speak'}
        </p>
      </div>
    </div>
  )
}
