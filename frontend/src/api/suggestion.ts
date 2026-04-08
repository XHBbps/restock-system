// 建议单 API 客户端
import client from './client'

export interface Suggestion {
  id: number
  status: 'draft' | 'partial' | 'pushed' | 'archived' | 'error'
  triggered_by: string
  total_items: number
  pushed_items: number
  failed_items: number
  global_config_snapshot: Record<string, unknown>
  created_at: string
  archived_at: string | null
}

export interface SuggestionItem {
  id: number
  commodity_sku: string
  commodity_id: string | null
  commodity_name: string | null
  main_image: string | null
  total_qty: number
  country_breakdown: Record<string, number>
  warehouse_breakdown: Record<string, Record<string, number>>
  t_purchase: Record<string, string>
  t_ship: Record<string, string>
  overstock_countries: string[]
  velocity_snapshot: Record<string, number> | null
  sale_days_snapshot: Record<string, number> | null
  urgent: boolean
  push_blocker: string | null
  push_status: 'pending' | 'pushed' | 'push_failed' | 'blocked'
  saihu_po_number: string | null
  push_error: string | null
  push_attempt_count: number
  pushed_at: string | null
}

export interface SuggestionDetail extends Suggestion {
  items: SuggestionItem[]
}

export interface SuggestionItemPatch {
  total_qty?: number
  country_breakdown?: Record<string, number>
  warehouse_breakdown?: Record<string, Record<string, number>>
  t_purchase?: Record<string, string>
  t_ship?: Record<string, string>
}

export async function listSuggestions(params: {
  status?: string
  date_from?: string
  date_to?: string
  sku?: string
  page?: number
  page_size?: number
}): Promise<{ items: Suggestion[]; total: number }> {
  const { data } = await client.get('/api/suggestions', { params })
  return data
}

export async function getCurrentSuggestion(): Promise<SuggestionDetail> {
  const { data } = await client.get<SuggestionDetail>('/api/suggestions/current')
  return data
}

export async function getSuggestion(id: number): Promise<SuggestionDetail> {
  const { data } = await client.get<SuggestionDetail>(`/api/suggestions/${id}`)
  return data
}

export async function patchSuggestionItem(
  suggestionId: number,
  itemId: number,
  patch: SuggestionItemPatch
): Promise<SuggestionItem> {
  const { data } = await client.patch<SuggestionItem>(
    `/api/suggestions/${suggestionId}/items/${itemId}`,
    patch
  )
  return data
}

export async function pushItems(
  suggestionId: number,
  itemIds: number[]
): Promise<{ task_id: number; existing: boolean }> {
  const { data } = await client.post<{ task_id: number; existing: boolean }>(
    `/api/suggestions/${suggestionId}/push`,
    { item_ids: itemIds }
  )
  return data
}

export async function archiveSuggestion(id: number): Promise<void> {
  await client.post(`/api/suggestions/${id}/archive`)
}
