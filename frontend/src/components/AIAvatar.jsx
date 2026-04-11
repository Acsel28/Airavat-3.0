/**
 * AIAvatar – animated SVG face that reacts to speaking / listening / idle state.
 * States: 'idle' | 'listening' | 'speaking'
 */
import React from 'react'

export default function AIAvatar({ state = 'idle', livenessScore = 0 }) {
  const isSpeaking  = state === 'speaking'
  const isListening = state === 'listening'

  // Colour shifts with state
  const coreGlow  = isSpeaking  ? '#818cf8' : isListening ? '#6ee7b7' : '#4b5563'
  const ringColor = isSpeaking  ? 'rgba(129,140,248,0.3)' : isListening ? 'rgba(110,231,183,0.3)' : 'rgba(75,85,99,0.15)'

  return (
    <div className="relative flex items-center justify-center" style={{ width: 160, height: 160 }}>

      {/* Outer animated ring */}
      <div
        className="absolute rounded-full transition-all duration-700"
        style={{
          width: 160, height: 160,
          border: `2px solid ${ringColor}`,
          boxShadow: isSpeaking || isListening
            ? `0 0 32px ${ringColor}, 0 0 8px ${ringColor}`
            : 'none',
          animation: (isSpeaking || isListening) ? 'pulse 2s ease-in-out infinite' : 'none',
        }}
      />

      {/* Ripple rings when speaking */}
      {isSpeaking && (
        <>
          <div className="absolute rounded-full animate-ripple"
            style={{ width: 120, height: 120, border: '1px solid rgba(129,140,248,0.4)' }} />
          <div className="absolute rounded-full animate-ripple"
            style={{ width: 120, height: 120, border: '1px solid rgba(129,140,248,0.4)', animationDelay: '0.5s' }} />
        </>
      )}

      {/* Listening pulse */}
      {isListening && (
        <div className="absolute rounded-full animate-ripple"
          style={{ width: 120, height: 120, border: '1px solid rgba(110,231,183,0.5)' }} />
      )}

      {/* Orbit dots */}
      <div className="absolute" style={{ width: 120, height: 120 }}>
        <div className="orbit-dot absolute"
          style={{
            width: 8, height: 8, borderRadius: '50%',
            background: coreGlow,
            top: '50%', left: '50%',
            marginTop: -4, marginLeft: -4,
            opacity: isSpeaking || isListening ? 1 : 0.3,
            transition: 'background 0.5s, opacity 0.5s',
          }}
        />
        <div className="orbit-dot-2 absolute"
          style={{
            width: 5, height: 5, borderRadius: '50%',
            background: '#6ee7b7',
            top: '50%', left: '50%',
            marginTop: -2.5, marginLeft: -2.5,
            opacity: isListening ? 1 : 0.2,
            transition: 'opacity 0.5s',
          }}
        />
      </div>

      {/* Core face SVG */}
      <svg
        width={110} height={110}
        viewBox="0 0 110 110"
        className="relative z-10 animate-float"
      >
        {/* Gradient defs */}
        <defs>
          <radialGradient id="faceGrad" cx="40%" cy="35%">
            <stop offset="0%"   stopColor={isSpeaking ? '#a5b4fc' : '#6ee7b7'} />
            <stop offset="100%" stopColor={isSpeaking ? '#4338ca' : '#059669'} />
          </radialGradient>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Face circle */}
        <circle cx="55" cy="55" r="44"
          fill="url(#faceGrad)"
          filter="url(#glow)"
          style={{ transition: 'all 0.5s' }}
        />

        {/* Inner face highlight */}
        <circle cx="45" cy="42" r="18" fill="white" opacity="0.06" />

        {/* Eyes */}
        <ellipse cx="40" cy="46" rx="5" ry={isSpeaking ? 3 : 5}
          fill={isSpeaking ? '#fff' : '#0a0a0f'}
          style={{ transition: 'ry 0.15s' }}
        />
        <ellipse cx="70" cy="46" rx="5" ry={isSpeaking ? 3 : 5}
          fill={isSpeaking ? '#fff' : '#0a0a0f'}
          style={{ transition: 'ry 0.15s' }}
        />

        {/* Eye shine */}
        <circle cx="42" cy="43" r="1.5" fill="white" opacity="0.8" />
        <circle cx="72" cy="43" r="1.5" fill="white" opacity="0.8" />

        {/* Eyebrows – raised when speaking */}
        <path
          d={isSpeaking ? 'M33 36 Q40 30 47 36' : 'M33 40 Q40 36 47 40'}
          stroke="#0a0a0f" strokeWidth="2" fill="none" strokeLinecap="round"
          style={{ transition: 'd 0.2s' }}
        />
        <path
          d={isSpeaking ? 'M63 36 Q70 30 77 36' : 'M63 40 Q70 36 77 40'}
          stroke="#0a0a0f" strokeWidth="2" fill="none" strokeLinecap="round"
          style={{ transition: 'd 0.2s' }}
        />

        {/* Mouth */}
        <g className={isSpeaking ? 'avatar-speaking' : ''}>
          {isSpeaking ? (
            /* Open mouth when speaking */
            <ellipse className="mouth" cx="55" cy="70" rx="10" ry="6" fill="#0a0a0f" />
          ) : (
            /* Smile when idle / listening */
            <path
              d={isListening ? 'M42 68 Q55 80 68 68' : 'M42 66 Q55 76 68 66'}
              stroke="#0a0a0f" strokeWidth="2.5" fill="none" strokeLinecap="round"
              style={{ transition: 'd 0.3s' }}
            />
          )}
        </g>

        {/* Listening indicator – small mic dots */}
        {isListening && (
          <>
            <circle cx="20" cy="55" r="3" fill="white" opacity="0.7">
              <animate attributeName="r" values="3;5;3" dur="0.8s" repeatCount="indefinite" />
            </circle>
            <circle cx="90" cy="55" r="3" fill="white" opacity="0.7">
              <animate attributeName="r" values="3;5;3" dur="0.8s" begin="0.4s" repeatCount="indefinite" />
            </circle>
          </>
        )}
      </svg>

      {/* State label */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 translate-y-6">
        <span className="text-xs font-mono px-2 py-0.5 rounded-full border"
          style={{
            color: coreGlow,
            borderColor: coreGlow,
            background: 'rgba(10,10,15,0.8)',
            transition: 'all 0.3s',
          }}
        >
          {state}
        </span>
      </div>
    </div>
  )
}