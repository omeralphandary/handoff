import { useEffect, useRef, useState } from 'react'
import type { GraphStatus } from '../api'

/**
 * SSE telemetry hook.
 * When inferring flips True → False, hold the True state for 600ms so the
 * purple pulse is visible even for fast inference calls. This prevents the
 * "analyzing" indicator from flickering on/off too rapidly.
 */
export function useTelemetry(graphId: string | null) {
  const [status, setStatus] = useState<GraphStatus>({
    active: false, inferring: false, last_capture_id: null, vram_mb: 0,
  })
  const holdTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!graphId) return
    const es = new EventSource(`/graphs/${graphId}/telemetry`)
    es.onmessage = (e) => {
      try {
        const next: GraphStatus = JSON.parse(e.data)
        setStatus(prev => {
          // If inference just finished, hold the inferring=true for 600ms
          if (prev.inferring && !next.inferring) {
            if (holdTimer.current) clearTimeout(holdTimer.current)
            holdTimer.current = setTimeout(() => {
              setStatus(s => ({ ...s, inferring: false }))
            }, 600)
            return { ...next, inferring: true }
          }
          return next
        })
      } catch {}
    }
    return () => {
      es.close()
      if (holdTimer.current) clearTimeout(holdTimer.current)
    }
  }, [graphId])

  return status
}
