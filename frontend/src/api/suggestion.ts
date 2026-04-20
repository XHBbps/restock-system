// 建议单 API 客户端
import type { SortOrder } from '@/utils/tableSort'

import client from './client'
import type { PageResult } from './data'

export interface AllocationExplanation {
  allocation_mode: 'matched' | 'fallback_even' | 'no_warehouse'
  matched_order_qty: number
  unknown_order_qty: number
  eligible_warehouses: string[]
}

export interface Suggestion {
  id: number
  status: 'draft' | 'archived' | 'error'
  triggered_by: string
  total_items: number
  snapshot_count: number
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
  allocation_snapshot: Record<string, AllocationExplanation> | null
  velocity_snapshot: Record<string, number> | null
  sale_days_snapshot: Record<string, number> | null
  urgent: boolean
  export_status: 'pending' | 'exported'
  exported_snapshot_id: number | null
  exported_at: string | null
}

export interface SuggestionDetail extends Suggestion {
  items: SuggestionItem[]
}

export interface SuggestionItemPatch {
  total_qty?: number
  country_breakdown?: Record<string, number>
  warehouse_breakdown?: Record<string, Record<string, number>>
}

export async function listSuggestions(params: {
  status?: string
  display_status?: 'pending' | 'exported' | 'archived' | 'error'
  date_from?: string
  date_to?: string
  sku?: string
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: SortOrder
}): Promise<PageResult<Suggestion>> {
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

export async function deleteSuggestion(suggestionId: number): Promise<void> {
  await client.delete(`/api/suggestions/${suggestionId}`)
}
