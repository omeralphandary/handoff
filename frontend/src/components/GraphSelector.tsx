import { useEffect, useState } from 'react'
import { api } from '../api'
import type { GraphMeta } from '../api'

interface Props {
  onSelect: (id: string, name: string) => void
}

export function GraphSelector({ onSelect }: Props) {
  const [graphs, setGraphs] = useState<GraphMeta[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.listGraphs().then(g => { setGraphs(g); setLoading(false) })
  }, [])

  return (
    <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-8">
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-3 mb-10">
          <div className="w-10 h-10 bg-blue-600 rounded-xl flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="5.5" height="12" rx="1.2" fill="white"/>
              <circle cx="3.75" cy="4.2" r="1.8" fill="#3b82f6"/>
              <circle cx="3.75" cy="4.2" r="0.7" fill="white"/>
              <rect x="8" y="5" width="5" height="8" rx="1.2" fill="white"/>
            </svg>
          </div>
          <div>
            <div className="text-xl font-bold text-white tracking-tight">Oversight Canvas</div>
            <div className="text-xs text-zinc-500">Visual pipeline editor</div>
          </div>
        </div>

        <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-widest">Select a pipeline</h2>

        {loading ? (
          <div className="text-zinc-600 text-sm">Loading…</div>
        ) : graphs.length === 0 ? (
          <div className="text-zinc-600 text-sm">
            No zones found.{' '}
            <a href="/zones/new" className="text-blue-400 hover:underline">Create one first</a>.
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {graphs.map(g => (
              <button key={g.id} onClick={() => onSelect(g.id, g.name)}
                className="w-full text-left px-5 py-4 rounded-xl bg-zinc-900 border border-zinc-800
                           hover:border-zinc-600 hover:bg-zinc-800 transition-colors group">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white group-hover:text-blue-300 transition-colors">
                    {g.name}
                  </span>
                  <div className="flex items-center gap-2">
                    {g.vram_mb != null && g.vram_mb > 0 && (
                      <span className="text-[11px] text-zinc-500">{g.vram_mb}MB</span>
                    )}
                    <span className={`w-2 h-2 rounded-full ${g.active ? 'bg-green-400' : 'bg-zinc-600'}`} />
                  </div>
                </div>
                <div className="text-xs text-zinc-500 mt-0.5 font-mono">{g.id}</div>
              </button>
            ))}
          </div>
        )}

        <div className="mt-6 pt-5 border-t border-zinc-800">
          <a href="/" className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors">
            ← Back to dashboard
          </a>
        </div>
      </div>
    </div>
  )
}
