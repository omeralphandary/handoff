import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { GraphStatus } from '../api'

interface Props {
  zoneId: string
  cameraUrl: string
  polygon: number[][]
  initialStatus: GraphStatus
  onSave: (polygon: number[][]) => void
  onClose: () => void
}

export function PolygonEditorModal({ zoneId, cameraUrl, polygon, initialStatus, onSave, onClose }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)
  const [points, setPoints] = useState<number[][]>(polygon ?? [])
  const [loading, setLoading] = useState(false)
  const [zoneActive, setZoneActive] = useState(initialStatus.active)
  const [zoneLoading, setZoneLoading] = useState(false)
  const [showStream, setShowStream] = useState(false)
  const [hint, setHint] = useState('Click to add points · Right-click to remove last · Click first point to close')

  // Draw on canvas whenever points or image change
  useEffect(() => { redraw() }, [points])

  function redraw() {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const img = imgRef.current
    if (img && img.complete && img.naturalWidth) {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    } else {
      ctx.fillStyle = '#111'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.fillStyle = '#444'
      ctx.font = '13px sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Click "Load snapshot" to load camera frame', canvas.width / 2, canvas.height / 2)
    }

    if (points.length === 0) return
    const px = points.map(([nx, ny]) => [nx * canvas.width, ny * canvas.height])

    ctx.beginPath()
    ctx.moveTo(px[0][0], px[0][1])
    px.slice(1).forEach(([x, y]) => ctx.lineTo(x, y))
    if (points.length > 2) {
      ctx.closePath()
      ctx.fillStyle = 'rgba(96,165,250,0.18)'
      ctx.fill()
    }
    ctx.strokeStyle = '#60a5fa'
    ctx.lineWidth = 1.5
    ctx.stroke()

    px.forEach(([x, y], i) => {
      ctx.beginPath()
      ctx.arc(x, y, i === 0 ? 6 : 4, 0, Math.PI * 2)
      ctx.fillStyle = i === 0 ? '#60a5fa' : '#fff'
      ctx.fill()
      ctx.strokeStyle = '#60a5fa'
      ctx.lineWidth = 1.5
      ctx.stroke()
    })
  }

  async function startZone() {
    setZoneLoading(true)
    try {
      await api.deploy(zoneId)
      setZoneActive(true)
      // Auto-load a snapshot after a short settle time
      setTimeout(() => loadSnapshot(), 1500)
    } catch { setHint('Failed to start zone') }
    setZoneLoading(false)
  }

  async function stopZone() {
    setZoneLoading(true)
    try {
      await api.stop(zoneId)
      setZoneActive(false)
      setShowStream(false)
    } catch { setHint('Failed to stop zone') }
    setZoneLoading(false)
  }

  async function loadSnapshot() {
    const canvas = canvasRef.current
    if (!canvas) return
    setLoading(true)
    setShowStream(false)
    try {
      // Try running zone snapshot first
      let res = await fetch(`/zones/${zoneId}/snapshot`)
      if (!res.ok && cameraUrl) {
        const fd = new FormData()
        fd.append('camera_url', cameraUrl)
        res = await fetch('/zones/preview-frame', { method: 'POST', body: fd })
      }
      if (res.ok) {
        const blob = await res.blob()
        const img = new Image()
        img.onload = () => {
          canvas.height = Math.round(canvas.width * img.naturalHeight / img.naturalWidth)
          imgRef.current = img
          redraw()
        }
        img.src = URL.createObjectURL(blob)
      } else {
        setHint('Could not load snapshot — start the zone first or check the camera URL')
      }
    } catch { setHint('Snapshot failed') }
    setLoading(false)
  }

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current!
    const r = canvas.getBoundingClientRect()
    const nx = parseFloat(((e.clientX - r.left) / r.width).toFixed(4))
    const ny = parseFloat(((e.clientY - r.top) / r.height).toFixed(4))

    // Close polygon if clicking near first point
    if (points.length >= 3) {
      const [fx, fy] = [points[0][0] * r.width, points[0][1] * r.height]
      const dist = Math.hypot(e.clientX - r.left - fx, e.clientY - r.top - fy)
      if (dist < 12) { setPoints(p => [...p]); return } // already closed visually
    }
    setPoints(p => [...p, [nx, ny]])
  }

  function handleRightClick(e: React.MouseEvent<HTMLCanvasElement>) {
    e.preventDefault()
    setPoints(p => p.slice(0, -1))
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl w-full max-w-3xl mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <div>
            <div className="text-sm font-semibold text-white">Crop / ROI Editor</div>
            <div className="text-xs text-zinc-500 mt-0.5">Draw a polygon to restrict analysis to a region</div>
          </div>
          <button onClick={onClose} className="text-zinc-500 hover:text-white transition-colors">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Zone control bar */}
        <div className="px-5 py-2.5 border-b border-zinc-800 flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${zoneActive ? 'bg-green-400' : 'bg-zinc-600'}`} />
            <span className="text-[11px] text-zinc-500">{zoneActive ? 'Zone running' : 'Zone stopped'}</span>
          </div>
          <div className="flex gap-2 ml-auto">
            {!zoneActive ? (
              <button
                onClick={startZone}
                disabled={zoneLoading}
                className="btn-primary px-3 py-1 rounded-lg text-xs font-medium"
              >
                {zoneLoading ? 'Starting…' : 'Start zone'}
              </button>
            ) : (
              <>
                <button
                  onClick={() => setShowStream(s => !s)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    showStream
                      ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                      : 'btn-secondary border-transparent'
                  }`}
                >
                  {showStream ? 'Hide live' : 'Live view'}
                </button>
                <button
                  onClick={stopZone}
                  disabled={zoneLoading}
                  className="btn-danger px-3 py-1 rounded-lg text-xs font-medium"
                >
                  {zoneLoading ? 'Stopping…' : 'Stop zone'}
                </button>
              </>
            )}
          </div>
        </div>

        {/* Canvas / Live view */}
        <div className="p-4">
          <div className="relative bg-black rounded-lg overflow-hidden" style={{ lineHeight: 0 }}>
            {showStream && zoneActive ? (
              <img
                src={`/zones/${zoneId}/stream`}
                alt="Live view"
                className="w-full"
                style={{ display: 'block' }}
              />
            ) : (
              <canvas
                ref={canvasRef}
                width={800}
                className="w-full cursor-crosshair"
                style={{ display: 'block' }}
                onClick={handleClick}
                onContextMenu={handleRightClick}
              />
            )}
          </div>
          <p className="text-xs text-zinc-500 mt-2">{hint}</p>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-5 py-4 border-t border-zinc-800">
          <div className="flex gap-2">
            <button
              onClick={loadSnapshot}
              disabled={loading || showStream}
              className="btn-secondary px-3 py-1.5 rounded-lg text-xs font-medium"
            >
              {loading ? 'Loading…' : 'Load snapshot'}
            </button>
            <button
              onClick={() => setPoints([])}
              disabled={showStream}
              className="btn-secondary px-3 py-1.5 rounded-lg text-xs font-medium"
            >
              Clear
            </button>
          </div>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn-secondary px-3 py-1.5 rounded-lg text-xs font-medium">
              Cancel
            </button>
            <button
              onClick={() => { onSave(points); onClose() }}
              className="btn-primary px-4 py-1.5 rounded-lg text-xs font-semibold"
            >
              Save polygon
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
