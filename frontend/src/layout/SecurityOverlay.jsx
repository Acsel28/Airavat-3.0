import React from "react";

export default function SecurityOverlay({
  open,
  meetingTerminated,
  meetingEndMessage,
  securityAlertType,
  violationSecondsRemaining,
  violationCount,
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-6">
      <div className="max-w-2xl w-full rounded-3xl border border-rose-400/40 bg-slate-900 p-8 text-center shadow-xl">
        <h2 className="text-3xl font-display font-bold text-rose-300">
          Security Compliance Alert
        </h2>
        <p className="mt-3 text-base text-slate-200">
          {meetingTerminated
            ? meetingEndMessage || "Meeting ended due to multiple identity violations."
            : "Invalid face detected. Return within 30 seconds or the meeting will end."}
        </p>
        <p className="mt-2 text-xs font-mono text-slate-400">
          Reason: {securityAlertType || "none"}
        </p>
        <p className="mt-5 text-sm text-slate-200 font-medium">
          {meetingTerminated
            ? "Start a new session to continue."
            : `Timer: ${violationSecondsRemaining}s • Violations: ${violationCount}/3`}
        </p>
      </div>
    </div>
  );
}
