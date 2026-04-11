import React from "react";
import { Panel, Chip } from "../components/ui/surface.jsx";

function StatChip({ icon, label, value }) {
  return (
    <Chip className="flex items-center gap-2">
      <span className="text-slate-400">{icon}</span>
      <span className="text-[11px] font-mono text-slate-400 uppercase">{label}</span>
      <span className="text-sm font-semibold text-slate-100">{value}</span>
    </Chip>
  );
}

export default function TopStatusBar({
  minutes,
  seconds,
  riskScore,
  livenessScore,
  violationCount,
  sessionActive,
  onToggleSession,
}) {
  return (
    <Panel className="px-4 py-3 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3 flex-wrap">
        <StatChip
          icon={<span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" />}
          label="Session"
          value={`${minutes}:${seconds}`}
        />
        <Chip className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-slate-400 uppercase">Risk</span>
          <div className="w-32 h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{ width: `${Math.max(0, Math.min(100, riskScore))}%` }}
            />
          </div>
          <span className="text-sm font-semibold text-indigo-300">{riskScore}</span>
        </Chip>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <StatChip icon={<span>📱</span>} label="Device" value="Verified" />
        <StatChip icon={<span>📍</span>} label="Location" value="Mumbai, IN" />
        <StatChip
          icon={<span>✅</span>}
          label="Liveness"
          value={livenessScore >= 70 ? "OK" : "Check"}
        />
        <div className="px-3 py-2 rounded-full bg-indigo-500/10 border border-indigo-400/30 text-indigo-200 text-sm font-semibold">
          Violations: {violationCount}/3
        </div>
        <button
          onClick={onToggleSession}
          className={`px-4 py-2 rounded-full text-sm font-semibold transition-all ${
            sessionActive
              ? "bg-rose-500/10 text-rose-300 border border-rose-400/30"
              : "bg-indigo-500 text-white border border-indigo-400"
          }`}
        >
          {sessionActive ? "End Session" : "Start Session"}
        </button>
      </div>
    </Panel>
  );
}
