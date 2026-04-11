import React from "react";
import { Panel } from "../components/ui/surface.jsx";

function DataField({ label, value, progress }) {
  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-900/60 p-4">
      <p className="text-[11px] font-mono uppercase tracking-wider text-slate-400">{label}</p>
      <p className="text-2xl font-display font-semibold text-slate-100 mt-1">{value}</p>
      {typeof progress === "number" && (
        <div className="mt-3 flex items-center gap-2">
          <div className="h-2 rounded-full bg-slate-700 flex-1 overflow-hidden">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{ width: `${Math.max(0, Math.min(100, progress))}%` }}
            />
          </div>
          <span className="text-[11px] font-mono text-slate-400">{Math.round(progress)}%</span>
        </div>
      )}
    </div>
  );
}

export default function LeftOperationsRail({
  livenessScore,
  avgAge,
  avatarState,
}) {
  return (
    <section className="space-y-4">
      <Panel className="p-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-300 grid place-content-center text-lg">◎</div>
          <div>
            <h2 className="text-2xl font-display font-semibold text-slate-100 leading-tight">Data Extraction</h2>
            <p className="text-sm text-slate-400">Real-time identity and profile capture</p>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          <DataField label="Full Name" value="Authorized User" progress={livenessScore} />
          <DataField label="Age" value={typeof avgAge === "number" ? `${Math.round(avgAge)} yrs` : "—"} />
          <DataField label="Monthly Income" value="—" />
          <DataField label="Loan Purpose" value="—" />
        </div>
      </Panel>

      <Panel className="p-4 space-y-3">
        <h3 className="text-xl font-display font-semibold text-slate-100">Consent & Compliance</h3>
        <div className="rounded-xl border border-amber-300/30 bg-amber-500/10 px-3 py-2 text-amber-200 text-sm">
          {avatarState === "listening" ? "Listening for consent..." : "Monitoring identity compliance"}
        </div>
        <p className="text-xs font-mono uppercase text-slate-400">Audit log</p>
        <ul className="text-sm text-slate-300 space-y-1">
          <li>00:12 Session started</li>
          <li>00:18 Identity verification initiated</li>
          <li>00:34 KYC data extraction started</li>
          <li>01:05 Liveness and voice linked</li>
        </ul>
      </Panel>
    </section>
  );
}
