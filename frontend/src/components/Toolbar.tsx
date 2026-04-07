import { useState } from 'react'
import type { GraphStatus, GraphMeta } from '../api'

interface Props {
  graphId: string
  graphName: string
  allGraphs: GraphMeta[]
  status: GraphStatus
  vramRequired: number
  saving: boolean
  saveMsg: string
  validationIssue: string | null
  onSave: () => void
  onDeploy: () => void
  onStop: () => void
  onTrigger: () => void
  onExport: () => void
  onSelect: (id: string, name: string) => void
  onBack: () => void
}

export function Toolbar({
  graphId, graphName, allGraphs, status, vramRequired,
  saving, saveMsg, validationIssue, onSave,
  onDeploy, onStop, onTrigger, onExport, onSelect, onBack,
}: Props) {
  const GPU_BUDGET_MB = 6000
  const vramPct = Math.min(100, Math.round(vramRequired / GPU_BUDGET_MB * 100))
  const vramColor = vramPct > 80 ? 'text-red-400' : vramPct > 50 ? 'text-yellow-400' : 'text-green-400'

  const [switcherOpen, setSwitcherOpen] = useState(false)

  return (
    <div className="h-12 flex-shrink-0 bg-zinc-900 border-b border-zinc-800 flex items-center px-3 gap-2">

      {/* Dashboard button — prominent */}
      <button
        onClick={onBack}
        title="Back to dashboard"
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg
                   bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 hover:border-zinc-500
                   text-zinc-300 hover:text-white text-xs font-medium transition-colors flex-shrink-0"
      >
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <path d="M1 6.5h11M1 6.5L5 2.5M1 6.5L5 10.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        Dashboard
      </button>

      <div className="h-5 w-px bg-zinc-700" />

      {/* Pipeline switcher */}
      <div className="relative">
        <button
          onClick={() => setSwitcherOpen(v => !v)}
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-zinc-800 transition-colors group"
        >
          <div className="w-5 h-5 bg-blue-600 rounded-md flex items-center justify-center flex-shrink-0">
            <svg width="11" height="11" viewBox="0 0 14 14" fill="none">
              <rect x="1" y="1" width="5.5" height="12" rx="1.2" fill="white"/>
              <rect x="8" y="5" width="5" height="8" rx="1.2" fill="white"/>
            </svg>
          </div>
          <span className="text-sm font-semibold text-white max-w-[140px] truncate">{graphName}</span>
          {allGraphs.length > 1 && (
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none" className="text-zinc-500 group-hover:text-zinc-300 transition-colors">
              <path d="M2 3.5l3 3 3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          )}
        </button>

        {switcherOpen && allGraphs.length > 1 && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setSwitcherOpen(false)} />
            <div className="absolute left-0 top-full mt-1 z-20 bg-zinc-900 border border-zinc-700 rounded-xl shadow-xl min-w-[220px] py-1 overflow-hidden">
              {allGraphs.map(g => (
                <button
                  key={g.id}
                  onClick={() => { onSelect(g.id, g.name); setSwitcherOpen(false) }}
                  className={`w-full text-left px-4 py-2.5 flex items-center justify-between
                    hover:bg-zinc-800 transition-colors gap-3
                    ${g.id === graphId ? 'text-white' : 'text-zinc-400 hover:text-white'}`}
                >
                  <span className="text-sm font-medium truncate">{g.name}</span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {g.id === graphId && (
                      <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                        <path d="M2 5.5l3 3 4-5" stroke="#60a5fa" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                    <span className={`w-1.5 h-1.5 rounded-full ${g.active ? 'bg-green-400' : 'bg-zinc-600'}`} />
                  </div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="h-5 w-px bg-zinc-700" />

      {/* VRAM */}
      {vramRequired > 0 && (
        <div className={`flex items-center gap-1 text-xs ${vramColor}`}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <rect x="1" y="3" width="10" height="6" rx="1" stroke="currentColor" strokeWidth="1.2"/>
            <path d="M3 3V2M6 3V2M9 3V2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
          </svg>
          {vramRequired}MB
        </div>
      )}

      {/* Zone status */}
      <div className="flex items-center gap-1.5">
        <span className={`w-2 h-2 rounded-full transition-colors ${
          !status.active       ? 'bg-zinc-600' :
          status.inferring     ? 'bg-purple-400 animate-pulse' :
                                 'bg-green-400'
        }`} />
        <span className="text-xs text-zinc-400">
          {status.active ? (status.inferring ? 'Analyzing…' : 'Connected') : 'Stopped'}
        </span>
      </div>

      <div className="flex-1" />

      {/* Actions */}
      <div className="flex items-center gap-2">
        {saveMsg && <span className="text-xs text-zinc-400">{saveMsg}</span>}
        <button onClick={onSave} disabled={saving} className="btn-secondary">
          {saving ? 'Saving…' : 'Save'}
        </button>
        <div className="h-4 w-px bg-zinc-700" />
        {!status.active ? (
          <button
            onClick={onDeploy}
            disabled={!!validationIssue}
            title={validationIssue ?? undefined}
            className="btn-primary disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Deploy
          </button>
        ) : (
          <>
            <button onClick={onTrigger} disabled={status.inferring} className="btn-secondary">Trigger</button>
            <button onClick={onStop} className="btn-danger">Stop</button>
          </>
        )}
        <button onClick={onExport} className="btn-ghost" title="Export graph JSON">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v8M4 6l3 3 3-3M2 10v2a1 1 0 001 1h8a1 1 0 001-1v-2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  )
}
