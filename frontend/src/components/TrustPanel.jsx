import React from 'react'

function statusColor(level) {
  if (level === 'success') return 'text-emerald-300 border-emerald-400/20 bg-emerald-400/10'
  if (level === 'warning') return 'text-amber-300 border-amber-400/20 bg-amber-400/10'
  return 'text-rose-300 border-rose-400/20 bg-rose-400/10'
}

function StatusRow({ icon, label, value, level = 'success', subtext }) {
  return (
    <div className={`rounded-2xl border p-4 ${statusColor(level)}`}>
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-950/30 text-lg">
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <p className="text-[11px] font-mono uppercase tracking-[0.24em] text-slate-400">{label}</p>
            <p className="text-sm font-semibold">{value}</p>
          </div>
          {subtext && <p className="mt-1 text-xs text-slate-300/80">{subtext}</p>}
        </div>
      </div>
    </div>
  )
}

export default function TrustPanel({
  data,
  ageData,
  ageError,
  riskScore,
  fraudScore,
  violationCount,
  securityMessage,
}) {
  const livenessScore = data ? Math.round((data.liveness_score || 0) * 100) : 0
  const avgAge = typeof ageData?.average_age === 'number' ? `${ageData.average_age} yrs` : 'Pending'
  const ageConfidence = typeof ageData?.confidence === 'number' ? `${ageData.confidence.toFixed(1)}% confidence` : ageError || 'Waiting for visible face'
  const identityMatch = data?.is_verified ? 'Verified' : data?.face_detected ? 'Reviewing' : 'Unavailable'

  return (
    <div className="card-glass flex h-full flex-col rounded-[2rem] border border-white/10 p-5 shadow-xl">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <p className="text-[10px] font-mono uppercase tracking-[0.28em] text-slate-500">Trust Panel</p>
          <h2 className="text-lg font-semibold text-white">Verification & Risk Insights</h2>
        </div>
        <div className="rounded-full border border-white/10 bg-slate-950/50 px-3 py-1 text-[10px] font-mono uppercase tracking-[0.22em] text-slate-400">
          Live scoring
        </div>
      </div>

      <div className="space-y-3">
        <StatusRow
          icon="👁"
          label="Face Detection"
          value={data?.face_detected ? 'Visible' : 'Missing'}
          level={data?.face_detected ? 'success' : 'critical'}
          subtext={securityMessage || 'Ensure your face remains centered and clearly visible.'}
        />
        <StatusRow
          icon="🛡"
          label="Liveness Score"
          value={`${livenessScore}%`}
          level={livenessScore >= 70 ? 'success' : livenessScore >= 40 ? 'warning' : 'critical'}
          subtext={data?.movement_detected ? 'Natural movement detected' : 'Minimal motion detected'}
        />
        <StatusRow
          icon="🧬"
          label="Identity Match"
          value={identityMatch}
          level={data?.is_verified ? 'success' : data?.face_detected ? 'warning' : 'critical'}
          subtext={data?.is_verified ? 'Session identity is locked and verified.' : 'Identity needs another clean frame.'}
        />
        <StatusRow
          icon="🎂"
          label="Age Prediction"
          value={avgAge}
          level={typeof ageData?.average_age === 'number' ? 'success' : 'warning'}
          subtext={ageConfidence}
        />
        <StatusRow
          icon="⚠"
          label="Fraud / Risk Score"
          value={`${riskScore}%`}
          level={riskScore < 35 ? 'success' : riskScore < 65 ? 'warning' : 'critical'}
          subtext={`Fraud exposure estimate ${fraudScore}%`}
        />
        <StatusRow
          icon="⏱"
          label="Violation Count"
          value={`${violationCount}/3`}
          level={violationCount === 0 ? 'success' : violationCount < 3 ? 'warning' : 'critical'}
          subtext={data?.violation_active ? `Grace timer active: ${data?.violation_seconds_remaining || 0}s remaining` : 'No active violation timer'}
        />
      </div>
    </div>
  )
}
