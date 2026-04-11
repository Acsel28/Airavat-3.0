import React, { useEffect, useRef, useState } from 'react'

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function ChatPanel({
  messages,
  loading,
  sessionActive,
  inputText,
  onInputChange,
  onSubmitText,
  onStateChange,
  onTranscriptChange,
}) {
  const [listening, setListening] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [supported, setSupported] = useState(true)
  const [voiceError, setVoiceError] = useState('')
  const scrollRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const recordingTimeoutRef = useRef(null)

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setSupported(false)
    }

    return () => {
      if (recordingTimeoutRef.current) {
        clearTimeout(recordingTimeoutRef.current)
      }
      streamRef.current?.getTracks?.().forEach((track) => track.stop())
    }
  }, [])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, loading])

  useEffect(() => {
    const onKey = (event) => {
      if (event.code === 'Space' && event.target === document.body && sessionActive) {
        event.preventDefault()
        if (listening) {
          stopListening()
        } else {
          startListening()
        }
      }
    }

    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [listening, sessionActive])

  const toDataUrl = (blob) => new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })

  const transcribeRecording = async (blob) => {
    const audioDataUrl = await toDataUrl(blob)
    const res = await fetch('/api/stt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audio: audioDataUrl, language: 'en' }),
    })

    if (!res.ok) {
      const detail = await res.text()
      throw new Error(`STT failed (${res.status}): ${detail}`)
    }

    const data = await res.json()
    const text = (data?.text || '').trim()
    onTranscriptChange?.(text)
    if (text) onSubmitText?.(text)
  }

  const stopListening = () => {
    const recorder = mediaRecorderRef.current
    if (!recorder) return
    if (recordingTimeoutRef.current) {
      clearTimeout(recordingTimeoutRef.current)
      recordingTimeoutRef.current = null
    }
    if (recorder.state === 'recording') {
      recorder.stop()
    }
  }

  const startListening = async () => {
    if (!supported || listening || transcribing || loading || !sessionActive) return

    try {
      setVoiceError('')
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder

      recorder.onstart = () => {
        setListening(true)
        onStateChange?.('listening')
        onTranscriptChange?.('')
      }

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) chunksRef.current.push(event.data)
      }

      recorder.onstop = async () => {
        setListening(false)
        setTranscribing(true)
        onStateChange?.('thinking')
        try {
          const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
          if (blob.size > 0) await transcribeRecording(blob)
          else setVoiceError('No audio captured. Please try again.')
        } catch (err) {
          console.error('Model STT error:', err)
          setVoiceError('Speech model failed. Check backend STT model setup.')
          onTranscriptChange?.('')
        } finally {
          setTranscribing(false)
          onStateChange?.('idle')
          streamRef.current?.getTracks?.().forEach((track) => track.stop())
          streamRef.current = null
          chunksRef.current = []
          mediaRecorderRef.current = null
        }
      }

      recorder.onerror = () => {
        setListening(false)
        setVoiceError('Audio capture failed. Please try again.')
        setTranscribing(false)
        onStateChange?.('idle')
        onTranscriptChange?.('')
        streamRef.current?.getTracks?.().forEach((track) => track.stop())
        streamRef.current = null
      }

      recorder.start()

      // Safety stop: prevents hanging in recording state if mouse/touch end is missed.
      recordingTimeoutRef.current = setTimeout(() => {
        stopListening()
      }, 10000)
    } catch (err) {
      console.error('Microphone access error:', err)
      setVoiceError('Microphone access denied or unavailable.')
      setListening(false)
      setTranscribing(false)
      onStateChange?.('idle')
    }
  }

  return (
    <div className="card-glass flex h-full flex-col rounded-[2rem] border border-white/10 shadow-xl">
      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.28em] text-slate-500">Conversation</p>
          <h2 className="text-lg font-semibold text-white">Onboarding Assistant</h2>
        </div>
        <div className="rounded-full border border-white/10 bg-slate-950/50 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-slate-400">
          {sessionActive ? 'Live Session' : 'Waiting'}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
        {messages.length === 0 && (
          <div className="rounded-2xl border border-dashed border-white/10 bg-slate-950/35 px-4 py-6 text-center text-sm text-slate-400">
            Start a session to begin. You can type or hold the mic to speak with the assistant.
          </div>
        )}

        {messages.map((message, index) => {
          const isAI = message.role === 'ai'

          return (
            <div
              key={`${message.timestamp || index}-${index}`}
              className={`flex transition-all duration-300 ${isAI ? 'justify-start' : 'justify-end'}`}
            >
              <div
                className={`max-w-[88%] rounded-[1.5rem] px-4 py-3 shadow-lg transition-all duration-300 ${
                  isAI
                    ? 'border border-indigo-400/20 bg-indigo-500/10 text-slate-100'
                    : 'border border-emerald-400/20 bg-emerald-500/10 text-white'
                }`}
              >
                <div className="mb-1 flex items-center gap-2">
                  <span className={`text-[10px] font-mono uppercase tracking-[0.22em] ${isAI ? 'text-indigo-200' : 'text-emerald-200'}`}>
                    {isAI ? 'AI Assistant' : 'You'}
                  </span>
                  {message.provider && (
                    <span className="rounded-full bg-white/5 px-2 py-0.5 text-[9px] font-mono uppercase tracking-[0.18em] text-slate-400">
                      {message.provider}
                    </span>
                  )}
                  <span className="text-[10px] text-slate-500">{formatTime(message.timestamp)}</span>
                </div>
                <p className="whitespace-pre-wrap text-sm leading-6">{message.text}</p>
                {message.suggestions?.length > 0 && (
                  <div className="mt-3 rounded-xl border border-white/10 bg-slate-950/30 p-3">
                    <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">Suggested Next Questions</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {message.suggestions.map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => onSubmitText?.(suggestion)}
                          className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-300 transition hover:border-indigo-400/40 hover:bg-indigo-400/10 hover:text-white"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}

        {loading && (
          <div className="flex justify-start">
            <div className="rounded-[1.5rem] border border-indigo-400/20 bg-indigo-500/10 px-4 py-3 text-slate-200 shadow-lg">
              <div className="mb-1 text-[10px] font-mono uppercase tracking-[0.22em] text-indigo-200">AI Assistant</div>
              <div className="flex items-center gap-2 text-sm">
                <span className="h-2 w-2 rounded-full bg-indigo-300 animate-bounce" />
                <span className="h-2 w-2 rounded-full bg-indigo-300 animate-bounce [animation-delay:120ms]" />
                <span className="h-2 w-2 rounded-full bg-indigo-300 animate-bounce [animation-delay:240ms]" />
                <span className="ml-2">AI is thinking...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-white/10 px-5 py-4">
        <div className="flex items-end gap-3">
          <button
            type="button"
            onMouseDown={startListening}
            onMouseUp={stopListening}
            onMouseLeave={stopListening}
            onBlur={stopListening}
            onTouchStart={startListening}
            onTouchEnd={stopListening}
            disabled={!supported || !sessionActive || loading}
            className={`flex h-12 w-12 items-center justify-center rounded-2xl border transition-all ${
              listening
                ? 'border-emerald-400/50 bg-emerald-400/15 text-emerald-100 shadow-[0_0_20px_rgba(52,211,153,0.18)]'
                : 'border-white/10 bg-slate-950/40 text-slate-300 hover:border-indigo-400/40 hover:text-white'
            } disabled:cursor-not-allowed disabled:opacity-40`}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </button>

          <div className="flex-1 rounded-[1.5rem] border border-white/10 bg-slate-950/40 p-2">
            <textarea
              rows={2}
              value={inputText}
              onChange={(event) => onInputChange?.(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  onSubmitText?.()
                }
              }}
              disabled={!sessionActive || loading}
              placeholder="Ask about onboarding, income verification, loan details, or next steps..."
              className="w-full resize-none bg-transparent px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500"
            />
            <div className="flex items-center justify-between px-3 pb-1 pt-2">
              <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">
                {listening ? 'Recording for model STT...' : transcribing ? 'Transcribing with model STT...' : 'Enter to send · Shift+Enter for new line'}
              </p>
              <button
                type="button"
                onClick={() => onSubmitText?.()}
                disabled={!sessionActive || !inputText.trim() || loading}
                className="rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 px-4 py-2 text-xs font-semibold text-white shadow-lg transition hover:scale-[1.02] hover:shadow-indigo-500/25 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </div>
        </div>
        {voiceError && (
          <p className="mt-3 text-xs text-amber-300">{voiceError}</p>
        )}
      </div>
    </div>
  )
}
