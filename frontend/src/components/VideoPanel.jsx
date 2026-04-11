import React from 'react'
import WebcamFeed from './WebcamFeed.jsx'

function MiniAvatar({ state, avatarVideoUrl }) {
  const speaking = state === 'speaking'
  const listening = state === 'listening'

  return (
    <div className="relative flex h-48 items-center justify-center overflow-hidden rounded-[2rem] border border-white/10 bg-slate-900/70">
      <div
        className={`absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(129,140,248,0.24),_transparent_55%)] transition-all duration-500 ${
          speaking ? 'opacity-100 scale-105' : listening ? 'opacity-80 scale-100' : 'opacity-60 scale-95'
        }`}
      />

      {avatarVideoUrl ? (
        <video
          key={avatarVideoUrl}
          src={avatarVideoUrl}
          autoPlay
          playsInline
          controls={false}
          className="relative z-10 h-full w-full object-cover"
        />
      ) : (
        <div className="relative z-10 flex h-32 w-32 items-center justify-center rounded-full bg-gradient-to-br from-slate-200 via-rose-100 to-amber-200 shadow-[0_0_40px_rgba(99,102,241,0.28)]">
          <div className="absolute top-5 h-10 w-16 rounded-b-full bg-slate-900" />
          <div className="absolute top-12 flex gap-7">
            <span className={`h-3 w-3 rounded-full bg-slate-900 transition-all ${listening ? 'scale-90' : 'scale-100'}`} />
            <span className={`h-3 w-3 rounded-full bg-slate-900 transition-all ${listening ? 'scale-90' : 'scale-100'}`} />
          </div>
          <div
            className={`absolute bottom-9 rounded-full bg-rose-900 transition-all duration-150 ${
              speaking ? 'h-4 w-8' : listening ? 'h-2 w-7' : 'h-2 w-8'
            }`}
          />
        </div>
      )}

      <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full border border-white/10 bg-slate-950/70 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-slate-200 backdrop-blur">
        <span className={`h-2 w-2 rounded-full ${speaking ? 'bg-indigo-400 animate-pulse' : listening ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
        {speaking ? 'Speaking' : listening ? 'Listening' : 'Idle'}
      </div>
    </div>
  )
}

export default function VideoPanel({
  sessionActive,
  sessionId,
  avatarState,
  avatarVideoUrl,
  assistantReply,
  onLivenessUpdate,
  onSecurityState,
  onAgeUpdate,
  onAgeError,
}) {
  return (
    <div className="flex h-full flex-col gap-5">
      <div className="card-glass overflow-hidden rounded-[2rem] border border-white/10 shadow-xl">
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-[0.28em] text-slate-500">Video</p>
            <h2 className="text-lg font-semibold text-white">Identity Capture</h2>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-slate-950/60 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-slate-300">
            <span className={`h-2 w-2 rounded-full ${sessionActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
            {sessionActive ? 'Camera Active' : 'Standby'}
          </div>
        </div>

        <div className="p-4">
          <div className={`overflow-hidden rounded-[2rem] border border-white/10 transition-all duration-500 ${
            sessionActive ? 'shadow-[0_0_40px_rgba(99,102,241,0.18)]' : ''
          }`}>
            <WebcamFeed
              onLivenessUpdate={onLivenessUpdate}
              onSecurityState={onSecurityState}
              onAgeUpdate={onAgeUpdate}
              onAgeError={onAgeError}
              active={sessionActive}
              sessionId={sessionId}
            />
          </div>
        </div>
      </div>

      <div className="card-glass rounded-[2rem] border border-white/10 p-4 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-[0.28em] text-slate-500">Avatar</p>
            <h3 className="text-base font-semibold text-white">AI Assistant</h3>
          </div>
          <div className="rounded-full bg-slate-950/60 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-slate-400">
            {avatarVideoUrl ? 'D-ID Active' : 'Visual Proxy'}
          </div>
        </div>

        <MiniAvatar state={avatarState} avatarVideoUrl={avatarVideoUrl} />

        <div className="mt-4 rounded-2xl border border-white/10 bg-slate-950/40 p-4">
          <p className="text-[10px] font-mono uppercase tracking-[0.22em] text-slate-500">Latest Reply</p>
          <p className="mt-2 text-sm leading-6 text-slate-200">
            {assistantReply || 'The assistant response will appear here once the conversation begins.'}
          </p>
        </div>
      </div>
    </div>
  )
}
