import React from 'react'

const STEPS = [
  { id: 'identity', label: 'Identity' },
  { id: 'verification', label: 'Verification' },
  { id: 'financial', label: 'Financial' },
  { id: 'decision', label: 'Decision' },
]

export default function ProgressBar({ current = 'identity' }) {
  const currentIndex = Math.max(0, STEPS.findIndex((step) => step.id === current))

  return (
    <div className="card-glass rounded-2xl border border-white/10 px-5 py-4 shadow-xl">
      <div className="flex items-center justify-between gap-3">
        {STEPS.map((step, index) => {
          const complete = index < currentIndex
          const active = index === currentIndex

          return (
            <div key={step.id} className="flex-1">
              <div className="flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full border text-xs font-mono transition-all duration-300 ${
                    complete
                      ? 'border-emerald-400/50 bg-emerald-400/15 text-emerald-200'
                      : active
                      ? 'border-indigo-400/60 bg-indigo-400/15 text-indigo-100 shadow-[0_0_18px_rgba(99,102,241,0.25)]'
                      : 'border-white/10 bg-slate-800/70 text-slate-400'
                  }`}
                >
                  {complete ? 'OK' : `0${index + 1}`}
                </div>
                <div className="min-w-0">
                  <p className={`text-xs font-mono uppercase tracking-[0.22em] ${active ? 'text-indigo-200' : 'text-slate-500'}`}>
                    Step {index + 1}
                  </p>
                  <p className={`text-sm font-semibold ${active ? 'text-white' : complete ? 'text-emerald-100' : 'text-slate-400'}`}>
                    {step.label}
                  </p>
                </div>
              </div>
              {index < STEPS.length - 1 && (
                <div className="mt-3 h-1 rounded-full bg-slate-800/80">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${
                      index < currentIndex ? 'bg-emerald-400' : active ? 'bg-indigo-400' : 'bg-transparent'
                    }`}
                    style={{ width: index < currentIndex ? '100%' : active ? '56%' : '0%' }}
                  />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
