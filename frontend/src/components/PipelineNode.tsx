import { Handle, Position } from '@xyflow/react'
import type { NodeProps } from '@xyflow/react'
import { NodeIcon } from './NodeIcon'

const CATEGORY_COLORS: Record<string, string> = {
  source:    'border-blue-500 bg-blue-500/10',
  filter:    'border-yellow-500 bg-yellow-500/10',
  inference: 'border-purple-500 bg-purple-500/10',
  sink:      'border-green-500 bg-green-500/10',
}

const CATEGORY_DOT: Record<string, string> = {
  source:    'bg-blue-500',
  filter:    'bg-yellow-500',
  inference: 'bg-purple-500',
  sink:      'bg-green-500',
}

export interface PipelineNodeData extends Record<string, unknown> {
  label: string
  icon: string
  category: string
  node_type: string
  vram_mb: number
  inferring?: boolean
  coming_soon?: boolean
  config?: Record<string, unknown>
}

export function PipelineNode({ data, selected }: NodeProps) {
  const d = data as PipelineNodeData
  const colorClass = CATEGORY_COLORS[d.category] ?? 'border-zinc-600 bg-zinc-800'
  const dotClass = CATEGORY_DOT[d.category] ?? 'bg-zinc-500'
  const isSource = d.category === 'source'
  const isSink = d.category === 'sink'

  return (
    <div className={`
      relative min-w-[160px] rounded-xl border px-4 py-3
      ${colorClass}
      ${selected ? 'ring-2 ring-white/30' : ''}
      transition-all cursor-pointer
    `}>
      {!isSource && (
        <Handle type="target" position={Position.Left}
          className="!w-3 !h-3 !border-2 !border-zinc-400 !bg-zinc-900" />
      )}

      <div className="flex items-center gap-2">
        <NodeIcon nodeType={d.node_type} category={d.category} size={16} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-white truncate">{d.label}</div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass}`} />
            <span className="text-[11px] text-zinc-400 capitalize">{d.category}</span>
            {d.vram_mb > 0 && (
              <span
                className="text-[10px] text-zinc-500 ml-1 cursor-default"
                title={`~${d.vram_mb} MB GPU VRAM required`}
              >
                {d.vram_mb}MB
              </span>
            )}
          </div>
        </div>
      </div>

      {d.inferring && !d.coming_soon && (
        <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
      )}
      {d.coming_soon && (
        <span className="absolute top-1.5 right-2 text-[9px] font-semibold text-zinc-500 bg-zinc-800 border border-zinc-700 px-1.5 py-0.5 rounded">
          soon
        </span>
      )}

      {!isSink && (
        <Handle type="source" position={Position.Right}
          className="!w-3 !h-3 !border-2 !border-zinc-400 !bg-zinc-900" />
      )}
    </div>
  )
}
