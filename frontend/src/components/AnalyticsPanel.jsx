/**
 * AnalyticsPanel – live session metrics: duration, message count, avg response time, liveness trend.
 */
import React, { useEffect, useState, useRef } from 'react'

function Stat({ label, value, unit, color = '#6ee7b7' }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] font-mono text-muted uppercase tracking-wider">{label}</span>
      <div className="flex items-baseline gap-1">
        <span className="text-xl font-display font-bold" style={{ color }}>{value}</span>
        {unit && <span className="text-xs text-muted font-body">{unit}</span>}
      </div>
    </div>
  )
}

function SparkLine({ data, color = '#6ee7b7' }) {
  if (!data || data.length < 2) return (
    <div className="flex items-center justify-center h-12 text-[10px] text-muted font-mono">
      waiting for data…
    </div>
  )

  const w = 200, h = 48
  const max = Math.max(...data, 1)
  const min = Math.min(...data)
  const range = max - min || 1

  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w
    const y = h - ((v - min) / range) * (h - 6) - 3
    return `${x},${y}`
  }).join(' ')

  const fillPts = `0,${h} ${pts} ${w},${h}`

  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ height: 48 }}>
      <defs>
        <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={fillPts} fill="url(#sparkFill)" />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* Last point dot */}
      {(() => {
        const last = data[data.length - 1]
        const x = w
        const y = h - ((last - min) / range) * (h - 6) - 3
        return <circle cx={x} cy={y} r="3" fill={color} />
      })()}
    </svg>
  )
}

export default function AnalyticsPanel({ sessionActive, messageCount, responseTimes, livenessSamples }) {
  const [elapsed, setElapsed] = useState(0)
  const startRef = useRef(null)

  // Track session duration
  useEffect(() => {
    if (sessionActive) {
      startRef.current = Date.now()
      const t = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startRef.current) / 1000))
      }, 1000)
      return () => clearInterval(t)
    } else {
      setElapsed(0)
      startRef.current = null
    }
  }, [sessionActive])

  const mins = String(Math.floor(elapsed / 60)).padStart(2, '0')
  const secs = String(elapsed % 60).padStart(2, '0')

  const avgResponse = responseTimes.length
    ? Math.round(responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length)
    : 0

  const currentLiveness = livenessSamples.length
    ? Math.round(livenessSamples[livenessSamples.length - 1] * 100)
    : 0

  return (
    <div className="card-glass rounded-2xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-display font-semibold text-gray-300 uppercase tracking-widest">
          Analytics
        </h3>
        {sessionActive && (
          <span className="text-[10px] font-mono text-accent border border-accent/30 px-2 py-0.5 rounded-full bg-accent/10">
            LIVE
          </span>
        )}
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-3">
        <Stat
          label="Duration"
          value={`${mins}:${secs}`}
          color={sessionActive ? '#6ee7b7' : '#6b7280'}
        />
        <Stat
          label="Messages"
          value={messageCount}
          color="#818cf8"
        />
        <Stat
          label="Avg RT"
          value={avgResponse || '–'}
          unit={avgResponse ? 'ms' : ''}
          color="#fbbf24"
        />
      </div>

      {/* Liveness sparkline */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-mono text-muted uppercase tracking-wider">Liveness trend</span>
          <span className="text-[10px] font-mono"
            style={{ color: currentLiveness >= 70 ? '#6ee7b7' : currentLiveness >= 40 ? '#fbbf24' : '#f87171' }}
          >
            {currentLiveness}%
          </span>
        </div>
        <SparkLine data={livenessSamples.map(v => v * 100)} color="#6ee7b7" />
      </div>

      {/* Response time sparkline */}
      {responseTimes.length > 1 && (
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-mono text-muted uppercase tracking-wider">Response time</span>
          </div>
          <SparkLine data={responseTimes} color="#818cf8" />
        </div>
      )}
    </div>
  )
}
