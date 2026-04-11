/**
 * WebcamFeed – captures webcam frames every 2s, sends to /analyze-frame,
 * and draws a face detection overlay on a second canvas layered over the video.
 */
import React, { useRef, useEffect, useState, useCallback } from 'react'

const CAPTURE_INTERVAL_MS = 2000
const AGE_SAMPLE_COUNT = 5
const AGE_FRAME_GAP_MS = 500
const AGE_PREDICTION_INTERVAL_MS = 8000

export default function WebcamFeed({ onLivenessUpdate, onAgeUpdate, onAgeError, active, sessionId }) {
  const videoRef      = useRef(null)
  const captureCanvas = useRef(null)   // hidden – for grabbing frames
  const overlayCanvas = useRef(null)   // visible overlay drawn on top of video
  const streamRef     = useRef(null)
  const timerRef      = useRef(null)
  const ageTimerRef   = useRef(null)
  const lastDataRef   = useRef(null)   // latest backend response

  const [cameraError, setCameraError] = useState(null)
  const [cameraReady, setCameraReady] = useState(false)

  // ── Start webcam ────────────────────────────────────────────────────────────
  useEffect(() => {
    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480, facingMode: 'user' },
          audio: false,
        })
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          videoRef.current.onloadedmetadata = () => {
            videoRef.current.play()
            setCameraReady(true)
          }
        }
      } catch (err) {
        setCameraError('Camera access denied. Please allow camera permissions.')
        console.error('Camera error:', err)
      }
    }
    startCamera()
    return () => { streamRef.current?.getTracks().forEach(t => t.stop()) }
  }, [])

  // ── Draw overlay (face box + score) ────────────────────────────────────────
  const drawOverlay = useCallback((data) => {
    const canvas = overlayCanvas.current
    const video  = videoRef.current
    if (!canvas || !video) return

    canvas.width  = video.clientWidth
    canvas.height = video.clientHeight
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!data) return

    const score  = Math.round(data.liveness_score * 100)
    const color  = score >= 70 ? '#6ee7b7' : score >= 40 ? '#fbbf24' : '#f87171'
    const shadow = score >= 70 ? 'rgba(110,231,183,0.5)' : score >= 40 ? 'rgba(251,191,36,0.5)' : 'rgba(248,113,113,0.5)'
    const w = canvas.width, h = canvas.height

    if (data.face_detected) {
      // Approximate centred face box
      const bx = w * 0.325, by = h * 0.08, bw = w * 0.35, bh = h * 0.75
      const cs = 20

      ctx.strokeStyle = color
      ctx.lineWidth   = 2
      ctx.shadowColor = shadow
      ctx.shadowBlur  = 8
      ctx.lineCap     = 'round'

      // Corner brackets
      [[bx, by, 1, 1],[bx+bw, by, -1, 1],[bx, by+bh, 1, -1],[bx+bw, by+bh, -1, -1]]
        .forEach(([x, y, hd, vd]) => {
          ctx.beginPath()
          ctx.moveTo(x + hd*cs, y)
          ctx.lineTo(x, y)
          ctx.lineTo(x, y + vd*cs)
          ctx.stroke()
        })

      // Score badge
      ctx.shadowBlur = 0
      const label = `LIVE  ${score}`
      ctx.font = 'bold 11px "JetBrains Mono", monospace'
      const tw  = ctx.measureText(label).width + 16
      const bbx = bx + bw/2 - tw/2, bby = by + 12
      ctx.fillStyle = 'rgba(10,10,15,0.75)'
      ctx.beginPath()
      ctx.roundRect(bbx, bby - 12, tw, 20, 4)
      ctx.fill()
      ctx.fillStyle = color
      ctx.fillText(label, bbx + 8, bby + 4)
    }

    // Movement dot
    if (data.movement_detected) {
      ctx.shadowColor = '#818cf8'
      ctx.shadowBlur  = 10
      ctx.fillStyle   = '#818cf8'
      ctx.beginPath()
      ctx.arc(w - 20, 20, 5, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0
    }
  }, [])

  // ── Animate overlay at 60fps ─────────────────────────────────────────────────
  useEffect(() => {
    let rafId
    const loop = () => { drawOverlay(lastDataRef.current); rafId = requestAnimationFrame(loop) }
    if (cameraReady) rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafId)
  }, [cameraReady, drawOverlay])

  // ── Capture & analyze ───────────────────────────────────────────────────────
  const captureAndAnalyze = useCallback(async () => {
    if (!videoRef.current || !captureCanvas.current || !cameraReady) return
    const video = videoRef.current, canvas = captureCanvas.current
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    const ctx = canvas.getContext('2d')
    ctx.translate(canvas.width, 0); ctx.scale(-1, 1)
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    const b64 = canvas.toDataURL('image/jpeg', 0.7)
    try {
      const res  = await fetch('/analyze-frame', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: b64, session_id: sessionId }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      lastDataRef.current = data
      onLivenessUpdate(data)
    } catch (err) { console.warn('Frame analysis error:', err) }
  }, [cameraReady, onLivenessUpdate, sessionId])

  const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms))

  const captureAgeFrames = useCallback(async (count = AGE_SAMPLE_COUNT) => {
    if (!videoRef.current || !captureCanvas.current || !cameraReady) return []
    const frames = []
    const video = videoRef.current
    const canvas = captureCanvas.current
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    const ctx = canvas.getContext('2d')

    for (let i = 0; i < count; i++) {
      ctx.translate(canvas.width, 0)
      ctx.scale(-1, 1)
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      frames.push(canvas.toDataURL('image/jpeg', 0.75))
      if (i < count - 1) await sleep(AGE_FRAME_GAP_MS)
    }

    return frames
  }, [cameraReady])

  const captureAndPredictAge = useCallback(async () => {
    if (!cameraReady) return
    if (!lastDataRef.current?.face_detected) {
      onAgeError?.('Face not detected clearly enough for age prediction')
      return
    }

    try {
      const frames = await captureAgeFrames(AGE_SAMPLE_COUNT)
      if (frames.length === 0) return
      const res = await fetch('/predict-age', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frames }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        onAgeError?.(err?.detail || 'Age prediction failed')
        return
      }
      const data = await res.json()
      onAgeError?.('')
      onAgeUpdate?.(data)
    } catch (err) {
      console.warn('Age prediction error:', err)
      onAgeError?.('Age prediction unavailable')
    }
  }, [cameraReady, captureAgeFrames, onAgeUpdate, onAgeError])

  // ── Poll ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (active && cameraReady) {
      captureAndAnalyze()
      timerRef.current = setInterval(captureAndAnalyze, CAPTURE_INTERVAL_MS)
    } else {
      clearInterval(timerRef.current)
    }

    if (active && cameraReady) {
      captureAndPredictAge()
      ageTimerRef.current = setInterval(captureAndPredictAge, AGE_PREDICTION_INTERVAL_MS)
    } else {
      clearInterval(ageTimerRef.current)
    }

    return () => {
      clearInterval(timerRef.current)
      clearInterval(ageTimerRef.current)
    }
  }, [active, cameraReady, captureAndAnalyze, captureAndPredictAge])

  return (
    <div className="relative w-full rounded-2xl overflow-hidden bg-surface border border-border"
      style={{ aspectRatio: '4/3' }}>
      <video ref={videoRef} muted playsInline className="w-full h-full object-cover"
        style={{ transform: 'scaleX(-1)' }} />
      <canvas ref={overlayCanvas} className="absolute inset-0 w-full h-full pointer-events-none" />
      <canvas ref={captureCanvas} className="hidden" />

      {cameraError && (
        <div className="absolute inset-0 flex items-center justify-center bg-ink/90 p-6 text-center">
          <div><div className="text-4xl mb-3">📷</div><p className="text-sm text-muted">{cameraError}</p></div>
        </div>
      )}
      {!cameraReady && !cameraError && (
        <div className="absolute inset-0 flex items-center justify-center bg-ink/80">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-accent border-t-transparent animate-spin" />
            <p className="text-xs text-muted font-mono">Initialising camera…</p>
          </div>
        </div>
      )}
      {cameraReady && (
        <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-ink/70 px-2 py-1 rounded-full backdrop-blur-sm">
          <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
          <span className="text-xs font-mono text-accent">LIVE</span>
        </div>
      )}
      {cameraReady && !active && (
        <div className="absolute inset-0 flex items-center justify-center bg-ink/50 backdrop-blur-[2px]">
          <div className="text-center">
            <p className="text-xs font-mono text-muted">Session paused</p>
            <p className="text-[10px] text-muted/60 mt-1">Press Start Session to begin analysis</p>
          </div>
        </div>
      )}
      {cameraReady && (
        <div className="absolute bottom-3 right-3 bg-ink/70 px-2 py-1 rounded backdrop-blur-sm">
          <span className="text-[10px] font-mono text-muted/70">SPACE = mic</span>
        </div>
      )}
    </div>
  )
}
