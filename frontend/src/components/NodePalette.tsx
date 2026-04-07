import type { CatalogByCategory } from '../hooks/useCatalog'
import type { NodeCatalogEntry } from '../api'
import { NodeIcon } from './NodeIcon'

const CATEGORY_ORDER = ['source', 'filter', 'inference', 'sink']
const CATEGORY_LABEL: Record<string, string> = {
  source: 'Sources', filter: 'Filters', inference: 'Inference', sink: 'Sinks',
}
const CATEGORY_COLOR: Record<string, string> = {
  source: 'text-blue-400', filter: 'text-yellow-400',
  inference: 'text-purple-400', sink: 'text-green-400',
}

interface Props {
  byCategory: CatalogByCategory
  onDragStart: (entry: NodeCatalogEntry) => void
}

export function NodePalette({ byCategory, onDragStart }: Props) {
  return (
    <div className="w-52 flex-shrink-0 bg-zinc-900 border-r border-zinc-800 overflow-y-auto flex flex-col">
      <div className="px-4 py-3 border-b border-zinc-800">
        <span className="text-xs font-semibold text-zinc-500 uppercase tracking-widest">Nodes</span>
      </div>
      <div className="flex-1 py-2">
        {CATEGORY_ORDER.filter(c => byCategory[c]?.length).map(category => (
          <div key={category} className="mb-3">
            <div className={`px-4 py-1 text-[10px] font-semibold uppercase tracking-widest ${CATEGORY_COLOR[category]}`}>
              {CATEGORY_LABEL[category]}
            </div>
            {byCategory[category].map(entry => (
              <div
                key={entry.type}
                draggable
                onDragStart={() => onDragStart(entry)}
                className="mx-2 mb-1 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700
                           cursor-grab active:cursor-grabbing flex items-center gap-2
                           border border-transparent hover:border-zinc-600 transition-colors"
              >
                <NodeIcon nodeType={entry.type} category={entry.category} size={14} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs font-medium truncate ${entry.coming_soon ? 'text-zinc-500' : 'text-zinc-200'}`}>
                      {entry.label}
                    </span>
                    {entry.coming_soon && (
                      <span className="text-[9px] font-semibold text-zinc-600 bg-zinc-900 border border-zinc-700 px-1 py-px rounded flex-shrink-0">
                        soon
                      </span>
                    )}
                  </div>
                  {entry.vram_mb > 0 && (
                    <div className="text-[10px] text-zinc-500">{entry.vram_mb}MB VRAM</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
