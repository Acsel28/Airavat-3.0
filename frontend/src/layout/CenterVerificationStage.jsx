import React from "react";
import WebcamFeed from "../components/WebcamFeed.jsx";
import LivenessPanel from "../components/LivenessPanel.jsx";
import AnalyticsPanel from "../components/AnalyticsPanel.jsx";

export default function CenterVerificationStage({
  sessionId,
  sessionActive,
  onLivenessUpdate,
  onSecurityState,
  onAgeUpdate,
  onAgeError,
  livenessData,
  ageData,
  ageError,
  messageCount,
  responseTimes,
  livenessSamples,
}) {
  return (
    <section className="space-y-4">
      <div className="rounded-3xl border border-slate-700 shadow-sm overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 p-4">
        <WebcamFeed
          onLivenessUpdate={onLivenessUpdate}
          onSecurityState={onSecurityState}
          sessionId={sessionId}
          onAgeUpdate={onAgeUpdate}
          onAgeError={onAgeError}
          active={sessionActive}
        />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <LivenessPanel data={livenessData} ageData={ageData} ageError={ageError} />
        <AnalyticsPanel
          sessionActive={sessionActive}
          messageCount={messageCount}
          responseTimes={responseTimes}
          livenessSamples={livenessSamples}
        />
      </div>
    </section>
  );
}
