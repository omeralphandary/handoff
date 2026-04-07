import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow, Background, Controls, MiniMap,
  addEdge, useNodesState, useEdgesState,
} from '@xyflow/react'
import type {
  Connection, Node, Edge, ReactFlowInstance, OnConnect, IsValidConnection,
} from '@xyflow/react'
import { api } from './api'
import type { GraphDefinition, GraphMeta, NodeCatalogEntry } from './api'
import { useCatalog } from './hooks/useCatalog'
import { useTelemetry } from './hooks/useTelemetry'
import { PipelineNode } from './components/PipelineNode'
import type { PipelineNodeData } from './components/PipelineNode'
import { NodePalette } from './components/NodePalette'
import { InspectorPanel } from './components/InspectorPanel'
import { Toolbar } from './components/Toolbar'

const NODE_TYPES = { pipeline: PipelineNode }

/** Node types that count as a valid trigger gate before inference. */
const TRIGGER_TYPES = new Set([
  'trigger',
  'manual_trigger', 'motion_filter', 'yolo_filter',
  'time_interval_filter', 'time_of_day_filter',
])

const LOCAL_INFERENCE  = new Set(['ollama_inference'])
const CLOUD_INFERENCE  = new Set(['claude_inference', 'gemini_inference', 'custom_prompt'])

const CATEGORY_X: Record<string, number> = {
  source: 60, filter: 320, inference: 580, sink: 840,
}
const yOffset: Record<string, number> = {}

function entryToNode(entry: NodeCatalogEntry, id: string, config: Record<string, unknown> = {}): Node<PipelineNodeData> {
  const cat = entry.category
  yOffset[cat] = (yOffset[cat] ?? 80) + 130
  return {
    id,
    type: 'pipeline',
    position: { x: CATEGORY_X[cat] ?? 400, y: yOffset[cat] },
    data: {
      label: entry.label,
      icon: entry.icon,
      category: cat,
      node_type: entry.type,
      vram_mb: entry.vram_mb,
      coming_soon: entry.coming_soon ?? false,
      config: { ...config },
    },
  }
}

function graphDefToFlow(graphDef: GraphDefinition, catalog: NodeCatalogEntry[]) {
  Object.keys(yOffset).forEach(k => { delete yOffset[k] })
  const nodes: Node<PipelineNodeData>[] = graphDef.nodes.flatMap(nd => {
    const entry = catalog.find(e => e.type === nd.type)
    if (!entry) return []
    const node = entryToNode(entry, nd.id, nd.config)
    // Restore saved canvas position if present
    if (typeof nd.config._x === 'number' && typeof nd.config._y === 'number') {
      node.position = { x: nd.config._x, y: nd.config._y }
    }
    return [node]
  })
  const edges: Edge[] = graphDef.edges.map((ed, i) => ({
    id: `e-${i}`,
    source: ed.source,
    target: ed.target,
    style: { stroke: '#52525b', strokeWidth: 1.5 },
  }))
  return { nodes, edges }
}

interface Props {
  graphId: string
  graphName: string
  onSelect: (id: string, name: string) => void
  onBack: () => void
}

export function CanvasView({ graphId, graphName, onSelect, onBack }: Props) {
  const { catalog, byCategory } = useCatalog()
  const status = useTelemetry(graphId)

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [vramRequired, setVramRequired] = useState(0)
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [allGraphs, setAllGraphs] = useState<GraphMeta[]>([])
  const dragEntry = useRef<NodeCatalogEntry | null>(null)

  useEffect(() => {
    api.listGraphs().then(setAllGraphs).catch(() => {})
  }, [])

  useEffect(() => {
    if (!catalog.length) return
    api.getGraph(graphId).then(({ graph, vram_required_mb }) => {
      const { nodes: n, edges: e } = graphDefToFlow(graph, catalog)
      setNodes(n)
      setEdges(e)
      setVramRequired(vram_required_mb)
    })
  }, [graphId, catalog])

  // Pulse inference nodes during inference — edges stay static
  useEffect(() => {
    setNodes(nds => nds.map(n => {
      const d = n.data as PipelineNodeData
      if (d.category !== 'inference') return n
      return { ...n, data: { ...d, inferring: status.inferring } }
    }))
  }, [status.inferring])

  const onConnect: OnConnect = useCallback((connection: Connection) => {
    setEdges(eds => addEdge({ ...connection, style: { stroke: '#52525b', strokeWidth: 1.5 } }, eds))
  }, [])

  const onNodeClick = useCallback((_: unknown, node: Node) => setSelectedNode(node), [])
  const onPaneClick = useCallback(() => setSelectedNode(null), [])

  // Clear inspector if selected node was deleted
  useEffect(() => {
    if (selectedNode && !nodes.find(n => n.id === selectedNode.id)) {
      setSelectedNode(null)
    }
  }, [nodes])

  const onConfigChange = useCallback((nodeId: string, config: Record<string, unknown>) => {
    setNodes(nds => nds.map(n =>
      n.id === nodeId ? { ...n, data: { ...n.data, config } } : n
    ))
    setSelectedNode(prev =>
      prev?.id === nodeId ? { ...prev, data: { ...prev.data, config } } : prev
    )
  }, [])

  // Block connections to inference nodes that don't come from a trigger-type node.
  const isValidConnection = useCallback<IsValidConnection>((connection) => {
    const target = nodes.find(n => n.id === connection.target)
    if (!target) return true
    if ((target.data as PipelineNodeData).category === 'inference') {
      const source = nodes.find(n => n.id === connection.source)
      return !!source && TRIGGER_TYPES.has((source.data as PipelineNodeData).node_type)
    }
    return true
  }, [nodes])

  // Hybrid mode: detect trigger → [local_inference, cloud_inference] pairs.
  // Returns the trigger node IDs that have both a local and a cloud inference child.
  const hybridTriggerIds = useMemo(() => {
    const result = new Set<string>()
    const triggerChildren: Record<string, { local: boolean; cloud: boolean }> = {}
    for (const e of edges) {
      const src = nodes.find(n => n.id === e.source)
      const tgt = nodes.find(n => n.id === e.target)
      if (!src || !tgt) continue
      const srcType = (src.data as PipelineNodeData).node_type
      const tgtType = (tgt.data as PipelineNodeData).node_type
      if (!TRIGGER_TYPES.has(srcType)) continue
      if (!triggerChildren[e.source]) triggerChildren[e.source] = { local: false, cloud: false }
      if (LOCAL_INFERENCE.has(tgtType)) triggerChildren[e.source].local = true
      if (CLOUD_INFERENCE.has(tgtType)) triggerChildren[e.source].cloud = true
    }
    for (const [id, flags] of Object.entries(triggerChildren)) {
      if (flags.local && flags.cloud) result.add(id)
    }
    return result
  }, [nodes, edges])

  // Validation: every inference node must have a trigger-type node as its direct input.
  const validationIssue = useMemo(() => {
    const inferenceNodes = nodes.filter(n => (n.data as PipelineNodeData).category === 'inference')
    if (inferenceNodes.length === 0) return null
    for (const inf of inferenceNodes) {
      const incoming = edges.filter(e => e.target === inf.id)
      const hasTrigger = incoming.some(e => {
        const src = nodes.find(n => n.id === e.source)
        return src && TRIGGER_TYPES.has((src.data as PipelineNodeData).node_type)
      })
      if (!hasTrigger) {
        const label = (inf.data as PipelineNodeData).label
        return `"${label}" needs a trigger node (Manual / Motion / YOLO / Time)`
      }
    }
    return null
  }, [nodes, edges])

  // Derive styled edges — no state mutation, avoids infinite loop
  const styledEdges = useMemo(() => edges.map(e => {
    const isHybrid = hybridTriggerIds.has(e.source)
    const tgt = nodes.find(n => n.id === e.target)
    const tgtType = tgt ? (tgt.data as PipelineNodeData).node_type : ''
    const isHybridEdge = isHybrid && (LOCAL_INFERENCE.has(tgtType) || CLOUD_INFERENCE.has(tgtType))
    return { ...e, style: isHybridEdge ? { stroke: '#22d3ee', strokeWidth: 1.5 } : { stroke: '#52525b', strokeWidth: 1.5 } }
  }), [edges, hybridTriggerIds, nodes])

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [])

  const handleSave = useCallback(async () => {
    setSaving(true)
    setSaveMsg('')
    const graphDef: GraphDefinition = {
      nodes: nodes.map(n => {
        const d = n.data as PipelineNodeData
        return {
          id: n.id,
          type: d.node_type,
          config: { ...(d.config ?? {}), _x: n.position.x, _y: n.position.y } as Record<string, unknown>,
        }
      }),
      edges: edges.map(e => ({ source: e.source, target: e.target })),
    }
    try {
      const res = await api.updateGraph(graphId, graphDef)
      setSaveMsg(res.restart_required ? 'Saved — restart to apply' : 'Saved')
    } catch (err) {
      setSaveMsg('Save failed')
    } finally {
      setSaving(false)
      setTimeout(() => setSaveMsg(''), 3000)
    }
  }, [nodes, edges, graphId])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const entry = dragEntry.current
    if (!entry || !rfInstance) return
    const pos = rfInstance.screenToFlowPosition({ x: e.clientX, y: e.clientY })
    const id = `${entry.type}-${Date.now()}`
    const node = entryToNode(entry, id)
    node.position = pos

    if (entry.type === 'camera_source') {
      // Auto-add a crop_filter node to the right of the camera source
      const cropEntry = catalog.find(e => e.type === 'crop_filter')
      if (cropEntry) {
        const cropId = `crop_filter-${Date.now() + 1}`
        const cropNode = entryToNode(cropEntry, cropId)
        cropNode.position = { x: pos.x + 260, y: pos.y }
        const cropEdge: Edge = {
          id: `e-${id}-${cropId}`,
          source: id,
          target: cropId,
          style: { stroke: '#52525b', strokeWidth: 1.5 },
        }
        setNodes(nds => [...nds, node, cropNode])
        setEdges(eds => [...eds, cropEdge])
        setVramRequired(v => v + entry.vram_mb + cropEntry.vram_mb)
        dragEntry.current = null
        return
      }
    }

    setNodes(nds => [...nds, node])
    setVramRequired(v => v + entry.vram_mb)
    dragEntry.current = null
  }, [rfInstance, catalog])

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-200">
      <Toolbar
        graphId={graphId}
        graphName={graphName}
        allGraphs={allGraphs}
        status={status}
        vramRequired={vramRequired}
        saving={saving}
        saveMsg={saveMsg}
        validationIssue={validationIssue}
        onSave={handleSave}
        onDeploy={() => api.deploy(graphId)}
        onStop={() => api.stop(graphId)}
        onTrigger={() => api.trigger(graphId)}
        onExport={() => api.exportGraph(graphId)}
        onSelect={onSelect}
        onBack={onBack}
      />

      <div className="flex flex-1 min-h-0">
        <NodePalette
          byCategory={byCategory}
          onDragStart={entry => { dragEntry.current = entry }}
        />

        <div className="flex-1 min-w-0 relative" onDragOver={onDragOver} onDrop={onDrop}>
          {hybridTriggerIds.size > 0 && !validationIssue && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2
                            bg-cyan-500/10 border border-cyan-500/30 text-cyan-300
                            text-xs px-4 py-2 rounded-lg shadow-lg pointer-events-none">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none" className="flex-shrink-0">
                <path d="M6.5 1v5M6.5 8v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                <circle cx="6.5" cy="6.5" r="5.5" stroke="currentColor" strokeWidth="1.2"/>
              </svg>
              Hybrid mode — local inference first, cloud fallback on failure
            </div>
          )}
          {validationIssue && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2
                            bg-yellow-500/10 border border-yellow-500/40 text-yellow-300
                            text-xs px-4 py-2 rounded-lg shadow-lg pointer-events-none">
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none" className="flex-shrink-0">
                <path d="M6.5 2L12 11H1L6.5 2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                <path d="M6.5 6v2.5M6.5 9.8v.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
              {validationIssue}
            </div>
          )}
          <ReactFlow
            nodes={nodes}
            edges={styledEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onInit={setRfInstance}
            nodeTypes={NODE_TYPES}
            isValidConnection={isValidConnection}
            fitView
            colorMode="dark"
            deleteKeyCode={['Delete', 'Backspace']}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#27272a" gap={24} size={1} />
            <Controls className="!bg-zinc-800 !border-zinc-700" />
            <MiniMap
              className="!bg-zinc-900 !border-zinc-700"
              nodeColor={n => {
                const cat = (n.data as PipelineNodeData).category
                return cat === 'source' ? '#3b82f6'
                  : cat === 'filter' ? '#eab308'
                  : cat === 'inference' ? '#a855f7'
                  : '#22c55e'
              }}
            />
          </ReactFlow>
        </div>

        <InspectorPanel
          node={selectedNode}
          catalog={catalog}
          graphId={graphId}
          zoneId={graphId}
          sourceUrl={(() => {
            const sourceNode = nodes.find(n => (n.data as PipelineNodeData).node_type === 'camera_source')
            return (sourceNode?.data as PipelineNodeData | undefined)?.config?.camera_url as string ?? ''
          })()}
          status={status}
          onConfigChange={onConfigChange}
          onDeploy={() => { api.deploy(graphId).catch(() => {}) }}
          onStop={() => { api.stop(graphId).catch(() => {}) }}
        />
      </div>
    </div>
  )
}
