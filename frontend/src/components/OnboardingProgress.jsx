/**
 * OnboardingProgress – shows the onboarding step pipeline.
 * Steps advance based on detected intent from /process-text responses.
 */
import React from 'react'

export const STEPS = [
  { id: 'greeting',   label: 'Welcome',     icon: '👋', description: 'Introduce yourself' },
  { id: 'name',       label: 'Identity',    icon: '🪪', description: 'Share your name' },
  { id: 'role',       label: 'Role',        icon: '💼', description: 'Tell us your position' },
  { id: 'experience', label: 'Background',  icon: '🧠', description: 'Your experience level' },
  { id: 'question',   label: 'Q&A',         icon: '❓', description: 'Ask anything' },
  { id: 'done',       label: 'Complete',    icon: '✅', description: 'All set!' },
]

const STEP_ORDER = STEPS.map(s => s.id)

export function getStepIndex(intent) {
  const idx = STEP_ORDER.indexOf(intent)
  return idx === -1 ? 0 : idx
}

export default function OnboardingProgress({ currentIntent, completedIntents = [] }) {
  const currentIdx = getStepIndex(currentIntent)

  return (
    <div className="card-glass rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-display font-semibold text-gray-300 uppercase tracking-widest">
          Progress
        </h3>
        <span className="text-xs font-mono text-muted">
          {completedIntents.length} / {STEPS.length} steps
        </span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1 bg-border rounded-full mb-5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${(completedIntents.length / STEPS.length) * 100}%`,
            background: 'linear-gradient(90deg, #6ee7b7, #818cf8)',
          }}
        />
      </div>

      {/* Step list */}
      <div className="flex flex-col gap-1">
        {STEPS.map((step, i) => {
          const done    = completedIntents.includes(step.id)
          const active  = step.id === currentIntent
          const future  = !done && !active

          return (
            <div
              key={step.id}
              className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-all duration-300 ${
                active  ? 'bg-accent/10 border border-accent/25' :
                done    ? 'opacity-60' :
                          'opacity-30'
              }`}
            >
              {/* Icon / check */}
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm flex-shrink-0 transition-all ${
                done   ? 'bg-accent/20 border border-accent/40' :
                active ? 'bg-accent2/20 border border-accent2/40 animate-pulse-slow' :
                         'bg-border border border-border/60'
              }`}>
                {done ? '✓' : step.icon}
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p className={`text-xs font-display font-semibold ${
                  active ? 'text-white' : done ? 'text-gray-400' : 'text-muted'
                }`}>
                  {step.label}
                </p>
                {active && (
                  <p className="text-[10px] text-accent/70 font-body truncate">
                    {step.description}
                  </p>
                )}
              </div>

              {/* Active indicator */}
              {active && (
                <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse flex-shrink-0" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
