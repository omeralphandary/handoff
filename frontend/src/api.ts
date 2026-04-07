/** Thin API client — all calls go through Vite proxy → FastAPI */

export interface NodeCatalogEntry {
  type: string
  label: string
  category: 'source' | 'filter' | 'inference' | 'sink'
  icon: string
  vram_mb: number
  config_schema: Record<string, unknown>
  coming_soon?: boolean
}

export interface NodeDef {
  id: string
  type: string
  config: Record<string, unknown>
}

export interface EdgeDef {
  source: string
  target: string
}

export interface GraphDefinition {
  nodes: NodeDef[]
  edges: EdgeDef[]
}

export interface GraphStatus {
  active: boolean
  inferring: boolean
  last_capture_id: string | null
  vram_mb: number
}

export interface GraphMeta {
  id: string
  name: string
  active: boolean
  vram_mb: number | null
}

const BASE = ''  // proxied by Vite in dev, same-origin in prod

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export const api = {
  catalog: (): Promise<NodeCatalogEntry[]> =>
    req('/graphs/catalog/nodes'),

  listGraphs: (): Promise<GraphMeta[]> =>
    req('/graphs'),

  getGraph: (id: string): Promise<{ id: string; name: string; graph: GraphDefinition; vram_required_mb: number }> =>
    req(`/graphs/${id}`),

  deploy: (id: string): Promise<{ status: string; vram_mb: number }> =>
    req(`/graphs/${id}/deploy`, { method: 'POST' }),

  stop: (id: string): Promise<{ status: string }> =>
    req(`/graphs/${id}/stop`, { method: 'POST' }),

  restart: (id: string): Promise<unknown> =>
    req(`/graphs/${id}/restart`, { method: 'POST' }),

  trigger: (id: string): Promise<{ status: string }> =>
    req(`/graphs/${id}/trigger`, { method: 'POST' }),

  status: (id: string): Promise<GraphStatus> =>
    req(`/graphs/${id}/status`),

  updateGraph: (id: string, graph: GraphDefinition): Promise<{ status: string; persisted_fields: string[]; restart_required: boolean; message: string }> =>
    req(`/graphs/${id}`, { method: 'PUT', body: JSON.stringify({ graph }) }),

  exportGraph: (id: string): void => {
    window.open(`/graphs/${id}/export`, '_blank')
  },
}
