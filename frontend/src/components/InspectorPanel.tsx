import { useState } from 'react'
import type { Node } from '@xyflow/react'
import type { NodeCatalogEntry, GraphStatus } from '../api'
import type { PipelineNodeData } from './PipelineNode'
import { PolygonEditorModal } from './PolygonEditorModal'
import { NodeIcon } from './NodeIcon'

interface Props {
  node: Node | null
  catalog: NodeCatalogEntry[]
  graphId: string
  zoneId: string
  sourceUrl: string   // camera URL from the source node — for polygon snapshot
  status: GraphStatus
  onConfigChange: (nodeId: string, config: Record<string, unknown>) => void
  onDeploy: () => void
  onStop: () => void
}

export function InspectorPanel({ node, catalog, zoneId, sourceUrl, status, onConfigChange, onDeploy, onStop }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [polyOpen, setPolyOpen] = useState(false)

  if (!node) {
    return (
      <div className="w-64 flex-shrink-0 bg-zinc-900 border-l border-zinc-800 flex items-center justify-center">
        <p className="text-xs text-zinc-600 text-center px-4">
          Click a node<br />to configure it
        </p>
      </div>
    )
  }

  const d = node.data as PipelineNodeData
  const entry = catalog.find(e => e.type === d.node_type)
  const schema = entry?.config_schema as Record<string, unknown> | undefined
  const properties = (schema?.properties ?? {}) as Record<string, Record<string, unknown>>
  const config = (d.config ?? {}) as Record<string, unknown>
  const isCrop = d.node_type === 'crop_filter'
  const isCamera = d.node_type === 'camera_source'
  const isTrigger = d.node_type === 'trigger'
  const polygon = (config.polygon as number[][] | undefined) ?? []

  const TRIGGER_FIELDS: Record<string, string[]> = {
    manual:   ['mode'],
    motion:   ['mode', 'threshold_pct', 'cooldown_seconds'],
    interval: ['mode', 'interval_seconds'],
    by_class: ['mode', 'classes', 'confidence', 'threshold_pct', 'cooldown_seconds'],
  }
  const triggerMode = (config.mode as string | undefined) ?? 'manual'
  const visibleTriggerFields = new Set(TRIGGER_FIELDS[triggerMode] ?? ['mode'])

  const widthClass = expanded ? 'w-96' : 'w-64'

  return (
    <>
      <div className={`${widthClass} flex-shrink-0 bg-zinc-900 border-l border-zinc-800 overflow-y-auto flex flex-col transition-all duration-200`}>
        {/* Header */}
        <div className="px-4 py-3 border-b border-zinc-800 flex items-center gap-2">
          <NodeIcon nodeType={d.node_type} category={d.category} size={16} />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-white">{d.label}</div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-500 font-mono truncate">{d.node_type}</span>
              {d.vram_mb > 0 && (
                <span
                  className="text-[10px] font-medium text-purple-400 bg-purple-500/10 border border-purple-500/30 px-1.5 py-0.5 rounded"
                  title={`This node requires ~${d.vram_mb} MB of GPU VRAM to run. Make sure your GPU has enough headroom.`}
                >
                  {d.vram_mb} MB VRAM
                </span>
              )}
            </div>
          </div>
          {/* Expand toggle */}
          <button
            onClick={() => setExpanded(v => !v)}
            title={expanded ? 'Collapse' : 'Expand'}
            className="text-zinc-500 hover:text-zinc-300 transition-colors flex-shrink-0"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              {expanded
                ? <path d="M5 2H2v3M9 2h3v3M5 12H2V9M9 12h3V9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                : <path d="M2 5V2h3M9 2h3v3M2 9v3h3M12 9v3H9" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              }
            </svg>
          </button>
        </div>

        {/* Zone control + live view for camera_source */}
        {isCamera && (
          <div className="border-b border-zinc-800">
            {/* Status + start/stop */}
            <div className="px-4 py-3 flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 transition-colors ${
                !status.active   ? 'bg-zinc-600' :
                status.inferring ? 'bg-purple-400 animate-pulse' :
                                   'bg-green-400'
              }`} />
              <span className="text-xs text-zinc-400 flex-1">
                {status.active ? (status.inferring ? 'Analyzing…' : 'Connected') : 'Stopped'}
              </span>
              {!status.active ? (
                <button onClick={onDeploy} className="btn-primary px-3 py-1 rounded-lg text-xs font-medium">
                  Start
                </button>
              ) : (
                <button onClick={onStop} className="btn-danger px-3 py-1 rounded-lg text-xs font-medium">
                  Stop
                </button>
              )}
            </div>
            {/* Live stream preview */}
            {status.active && (
              <div className="px-4 pb-3">
                <div className="rounded-lg overflow-hidden bg-black" style={{ lineHeight: 0 }}>
                  <img src={`/zones/${zoneId}/stream`} alt="Live view" className="w-full" style={{ display: 'block' }} />
                </div>
              </div>
            )}
            {/* Camera settings */}
            <div className="px-4 py-3 flex flex-col gap-3">
              <p className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Camera Settings</p>
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-zinc-400">RTSP URL</label>
                <input
                  type="text"
                  value={String(config.url ?? '')}
                  onChange={e => onConfigChange(node.id, { ...config, url: e.target.value })}
                  placeholder="rtsp://..."
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs font-medium text-zinc-400">FPS Limit</label>
                <input
                  type="number"
                  value={String(config.fps_limit ?? 10)}
                  min={1} max={30} step={1}
                  onChange={e => onConfigChange(node.id, { ...config, fps_limit: parseFloat(e.target.value) })}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-md px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>
          </div>
        )}

        {/* Polygon editor shortcut for crop_filter */}
        {isCrop && (
          <div className="px-4 py-3 border-b border-zinc-800">
            <button
              onClick={() => setPolyOpen(true)}
              className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg
                         bg-blue-600/10 border border-blue-500/30 hover:bg-blue-600/20
                         text-blue-300 text-xs font-medium transition-colors"
            >
              <span className="flex items-center gap-2">
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M6.5 1L12 4.5v4L6.5 12 1 8.5v-4L6.5 1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                </svg>
                {polygon.length > 0 ? `Edit polygon (${polygon.length} pts)` : 'Draw ROI polygon'}
              </span>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            {polygon.length > 0 && (
              <button
                onClick={() => onConfigChange(node.id, { ...config, polygon: [] })}
                className="mt-2 text-[10px] text-zinc-500 hover:text-red-400 transition-colors w-full text-left px-1"
              >
                Clear polygon
              </button>
            )}
          </div>
        )}

        {/* Config fields */}
        {Object.keys(properties).length === 0 && !isCrop ? (
          <p className="px-4 py-3 text-xs text-zinc-500">No configuration options.</p>
        ) : (
          <div className="px-4 py-3 flex flex-col gap-4 overflow-y-auto">
            {Object.entries(properties)
              .filter(([key]) => !(isCrop && key === 'polygon'))
              .filter(([key]) => !isTrigger || visibleTriggerFields.has(key))
              .filter(([key]) => !(isCamera && ['url', 'fps_limit', 'source_id'].includes(key)))
              .map(([key, prop]) => (
                <div key={key} className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-zinc-400">
                    {String(prop.title ?? key)}
                  </label>
                  <ConfigField
                    prop={prop}
                    value={config[key] ?? prop.default ?? ''}
                    onChange={(val) => onConfigChange(node.id, { ...config, [key]: val })}
                    expanded={expanded}
                  />
                  {prop.description != null && (
                    <p className="text-[10px] text-zinc-600">{String(prop.description)}</p>
                  )}
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Polygon editor modal */}
      {polyOpen && (
        <PolygonEditorModal
          zoneId={zoneId}
          cameraUrl={sourceUrl}
          polygon={polygon}
          initialStatus={status}
          onSave={(poly) => onConfigChange(node.id, { ...config, polygon: poly })}
          onClose={() => setPolyOpen(false)}
        />
      )}
    </>
  )
}

function ConfigField({
  prop, value, onChange, expanded,
}: {
  prop: Record<string, unknown>
  value: unknown
  onChange: (val: unknown) => void
  expanded: boolean
}) {
  const inputClass =
    'w-full bg-zinc-800 border border-zinc-700 rounded-md px-2.5 py-1.5 ' +
    'text-xs text-zinc-200 focus:outline-none focus:border-blue-500'

  const enumVals = prop.enum as string[] | undefined
  if (enumVals) {
    return (
      <select value={String(value)} onChange={e => onChange(e.target.value)} className={inputClass}>
        {enumVals.map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    )
  }

  // Array of enum — render as tag checkboxes when expanded
  if (prop.type === 'array' && (prop.items as any)?.enum) {
    const opts = (prop.items as any).enum as string[]
    const selected = Array.isArray(value) ? (value as string[]) : []
    return (
      <div className={`flex flex-wrap gap-1.5 ${expanded ? '' : 'max-h-24 overflow-y-auto'}`}>
        {opts.map(opt => (
          <button
            key={opt}
            type="button"
            onClick={() => {
              const next = selected.includes(opt)
                ? selected.filter(s => s !== opt)
                : [...selected, opt]
              onChange(next)
            }}
            className={`px-2 py-0.5 rounded text-[11px] font-medium border transition-colors ${
              selected.includes(opt)
                ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                : 'bg-zinc-800 border-zinc-700 text-zinc-400 hover:border-zinc-500'
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    )
  }

  if (prop.type === 'array') {
    const arrVal = Array.isArray(value) ? (value as string[]).join(', ') : String(value)
    return (
      <input type="text" value={arrVal}
        onChange={e => onChange(e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
        placeholder="item1, item2, ..."
        className={inputClass} />
    )
  }

  if (prop.type === 'boolean') {
    return (
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={Boolean(value)}
          onChange={e => onChange(e.target.checked)}
          className="w-3.5 h-3.5 rounded accent-blue-500" />
        <span className="text-xs text-zinc-400">Enabled</span>
      </label>
    )
  }

  if (prop.type === 'integer' || prop.type === 'number') {
    return (
      <input type="number" value={String(value)}
        step={prop.type === 'integer' ? 1 : 0.01}
        onChange={e => onChange(prop.type === 'integer' ? parseInt(e.target.value) : parseFloat(e.target.value))}
        className={inputClass} />
    )
  }

  // Long text (prompts) — textarea when expanded
  if (prop.type === 'string' && expanded) {
    return (
      <textarea
        value={String(value)}
        onChange={e => onChange(e.target.value)}
        rows={5}
        className={inputClass + ' resize-y'}
      />
    )
  }

  return (
    <input type="text" value={String(value)}
      onChange={e => onChange(e.target.value)}
      className={inputClass} />
  )
}
