import React from "react";
import AIAvatar from "../components/AIAvatar.jsx";
import OnboardingProgress from "../components/OnboardingProgress.jsx";
import VoiceChat from "../components/VoiceChat.jsx";
import { Panel } from "../components/ui/surface.jsx";

export default function RightAssistantRail({
  avatarState,
  livenessScore,
  currentIntent,
  completedIntents,
  onStateChange,
  onIntentDetected,
  onResponseTime,
  onMessageCountChange,
  paused,
  sessionId,
}) {
  return (
    <section className="space-y-4">
      <Panel className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-2xl font-display font-semibold text-slate-100">AI Assistant</h3>
            <p className="text-sm text-slate-400">Neural Engine v4.2</p>
          </div>
          <span className="px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-200 border border-indigo-400/25 text-xs font-semibold">
            {avatarState === "listening" ? "Listening..." : avatarState === "speaking" ? "Speaking..." : "Standby"}
          </span>
        </div>
        <div className="mt-4 rounded-2xl bg-gradient-to-br from-indigo-600 to-sky-500 p-4 text-white">
          <div className="flex items-center justify-center">
            <AIAvatar state={avatarState} livenessScore={livenessScore} />
          </div>
        </div>
      </Panel>

      <OnboardingProgress
        currentIntent={currentIntent}
        completedIntents={completedIntents}
      />

      <VoiceChat
        onStateChange={onStateChange}
        onIntentDetected={onIntentDetected}
        onResponseTime={onResponseTime}
        onMessageCountChange={onMessageCountChange}
        paused={paused}
        sessionId={sessionId}
      />
    </section>
  );
}
