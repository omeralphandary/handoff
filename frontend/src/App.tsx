import { useState, useEffect, useRef } from 'react'
import { CanvasView } from './CanvasView'
import { api } from './api'

const LS_KEY = 'oversight_last_graph'

export default function App() {
  const [selected, setSelected] = useState<{ id: string; name: string } | null>(null)
  const [ready, setReady] = useState(false)
  const fromDashboard = useRef(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const deepLink = params.get('graph')

    if (deepLink) {
      // Deep-linked from dashboard
      fromDashboard.current = true
      api.getGraph(deepLink)
        .then(g => { setSelected({ id: deepLink, name: g.name }); setReady(true) })
        .catch(() => setReady(true))
      return
    }

    // Try last used graph from localStorage, then fall back to first in list
    const lastId = localStorage.getItem(LS_KEY)
    api.listGraphs().then(graphs => {
      const target = lastId ? graphs.find(g => g.id === lastId) : null
      const pick = target ?? graphs[0]
      if (pick) {
        api.getGraph(pick.id).then(g => {
          setSelected({ id: pick.id, name: g.name })
          setReady(true)
        }).catch(() => setReady(true))
      } else {
        // No graphs exist — send to zone creation
        window.location.href = '/zones/new'
      }
    }).catch(() => setReady(true))
  }, [])

  if (!ready) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-zinc-600 border-t-blue-400 rounded-full animate-spin" />
      </div>
    )
  }

  if (!selected) {
    window.location.href = '/'
    return null
  }

  const handleSelect = (id: string, name: string) => {
    localStorage.setItem(LS_KEY, id)
    fromDashboard.current = false
    setSelected({ id, name })
  }

  const handleBack = () => {
    if (fromDashboard.current) {
      window.location.href = `/zones/${selected.id}`
    } else {
      window.location.href = '/'
    }
  }

  return (
    <CanvasView
      graphId={selected.id}
      graphName={selected.name}
      onSelect={handleSelect}
      onBack={handleBack}
    />
  )
}
