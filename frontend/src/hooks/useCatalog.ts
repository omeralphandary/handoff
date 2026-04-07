import { useEffect, useState } from 'react'
import { api } from '../api'
import type { NodeCatalogEntry } from '../api'

export type CatalogByCategory = Record<string, NodeCatalogEntry[]>

export function useCatalog() {
  const [catalog, setCatalog] = useState<NodeCatalogEntry[]>([])
  const [byCategory, setByCategory] = useState<CatalogByCategory>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.catalog().then(entries => {
      setCatalog(entries)
      const grouped: CatalogByCategory = {}
      for (const e of entries) {
        ;(grouped[e.category] ??= []).push(e)
      }
      setByCategory(grouped)
      setLoading(false)
    })
  }, [])

  return { catalog, byCategory, loading }
}
