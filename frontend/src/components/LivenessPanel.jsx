/**
 * LivenessPanel – displays the liveness score with animated gauge.
 */
import React from 'react'

function ScoreGauge({ value }) {
  // value: 0–100
  const clamp    = Math.max(0, Math.min(100, value))
  const radius   = 38
  const circ     = 2 * Math.PI * radius
  const dash     = (clamp / 100) * circ
  const gap      = circ - dash

  const color =
    clamp >= 70 ? '#6ee7b7' :
    clamp >= 40 ? '#fbbf24' :
                  '#f87171'

  return (
    <div className="relative flex items-center justify-center" style={{ width: 100, height: 100 }}>
      <svg width={100} height={100} viewBox="0 0 100 100">
        {/* Track */}
        <circle cx="50" cy="50" r={radius}
          fill="none" stroke="#2a2a38" strokeWidth="6" />
        {/* Progress */}
        <circle cx="50" cy="50" r={radius}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeDasharray={`${dash} ${gap}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          style={{ transition: 'stroke-dasharray 0.6s cubic-bezier(0.4,0,0.2,1), stroke 0.4s' }}
        />
      </svg>
      {/* Value text */}
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-display font-bold" style={{ color }}>{clamp}</span>
        <span className="text-[9px] font-mono text-muted -mt-1">/ 100</span>
      </div>
    </div>
  )
}

function IndicatorRow({ label, active }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 border-b border-border/40 last:border-0">
      <span className="text-xs text-muted font-body">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full transition-all duration-300 ${
          active ? 'bg-accent shadow-[0_0_6px_#6ee7b7]' : 'bg-border'
        }`} />
        <span className={`text-[10px] font-mono ${active ? 'text-accent' : 'text-muted'}`}>
          {active ? 'YES' : 'NO'}
        </span>
      </div>
    </div>
  )
}

export default function LivenessPanel({ data, ageData, ageError }) {
  const score      = data ? Math.round(data.liveness_score * 100) : 0
  const faceOk     = data?.face_detected ?? false
  const movementOk = data?.movement_detected ?? false
  const diffScore  = data?.frame_diff_score ?? 0
  const avgAge = ageData?.average_age
  const ageConfidence = ageData?.confidence

  const status =
    score >= 70 ? { label: 'Verified', color: '#6ee7b7' } :
    score >= 40 ? { label: 'Checking…', color: '#fbbf24' } :
                  { label: 'No signal', color: '#f87171' }

  return (
    <div className="card-glass rounded-2xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-display font-semibold text-gray-300 uppercase tracking-widest">
          Liveness
        </h3>
        <span className="text-xs font-mono px-2 py-0.5 rounded-full border"
          style={{ color: status.color, borderColor: status.color + '55', background: status.color + '11' }}
        >
          {status.label}
        </span>
      </div>

      {/* Gauge */}
      <div className="flex justify-center">
        <ScoreGauge value={score} />
      </div>

      {/* Indicators */}
      <div>
        <IndicatorRow label="Face detected"   active={faceOk} />
        <IndicatorRow label="Movement"         active={movementOk} />
        <IndicatorRow label="Frame diff"
          active={diffScore > 0.01}
        />
      </div>

      {/* Raw diff value */}
      <div className="flex items-center justify-between text-[10px] font-mono text-muted">
        <span>Frame Δ</span>
        <span>{(diffScore * 100).toFixed(2)}%</span>
      </div>

      <div className="pt-1 border-t border-border/40">
        <div className="flex items-center justify-between text-xs font-body">
          <span className="text-muted">Predicted age</span>
          <span className="text-gray-200 font-semibold">
            {typeof avgAge === 'number' ? `${avgAge} yrs` : 'Waiting for face...'}
          </span>
        </div>
        <div className="flex items-center justify-between text-[10px] font-mono text-muted mt-1">
          <span>Age confidence</span>
          <span>{typeof ageConfidence === 'number' ? `${ageConfidence.toFixed(1)}%` : '--'}</span>
        </div>
        {ageError && (
          <p className="text-[10px] text-amber-300 mt-1.5">{ageError}</p>
        )}
      </div>
    </div>
  )
}