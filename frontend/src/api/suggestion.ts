import type { SortOrder } from '@/utils/tableSort'

import client from './client'
import type { PageResult } from './data'

export interface AllocationExplanation {
  allocation_mode: 'matched' | 'fallback_even' | 'no_warehouse'
  matched_order_qty: number
  unknown_order_qty: number
  eligible_warehouses: string[]
}

export interface CalculationInputsSnapshot {
  version: number
  generated_at: string
  demand_date: string
  target_days: number
  demand_days: number
  effective_target_days: number
  safety_stock_days: number
  purchase: {
    country_restock_qty_total: number
    country_restock_qty_by_country: Record<string, number>
    daily_velocity_total: number
    daily_velocity_by_country: Record<string, number>
    safety_stock_qty: number
    local_stock_available: number
    local_stock_reserved: number
    local_stock_total: number
    raw_purchase_qty: number
    final_purchase_qty: number
  }
  restock: {
    countries: Record<
      string,
      {
        effective_target_days: number
        daily_velocity: number
        overseas_available: number
        overseas_reserved: number
        in_transit: number
        overseas_stock_total: number
        target_stock_qty: number
        raw_restock_qty: number
        final_restock_qty: number
        sale_days: number | null
        restock_date: string | null
      }
    >
  }
}

export type SuggestionDisplayStatus = '未导出' | '已导出' | '已归档'
// 机器可读 code（4 档），供 tag 色映射 / i18n；label 保留 3 档 UX 兼容
export type SuggestionDisplayStatusCode = 'pending' | 'exported' | 'archived' | 'error'

export interface Suggestion {
  id: number
  status: 'draft' | 'archived' | 'error'
  triggered_by: string
  total_items: number
  procurement_item_count: number
  restock_item_count: number
  procurement_snapshot_count: number
  restock_snapshot_count: number
  archived_trigger: string | null
  procurement_display_status: SuggestionDisplayStatus
  restock_display_status: SuggestionDisplayStatus
  procurement_display_status_code: SuggestionDisplayStatusCode
  restock_display_status_code: SuggestionDisplayStatusCode
  global_config_snapshot: Record<string, unknown>
  created_at: string
  archived_at: string | null
}

export interface SuggestionItem {
  id: number
  commodity_sku: string
  commodity_name: string | null
  main_image: string | null
  total_qty: number
  country_breakdown: Record<string, number>
  warehouse_breakdown: Record<string, Record<string, number>>
  restock_dates: Record<string, string | null>
  allocation_snapshot: Record<string, AllocationExplanation> | null
  velocity_snapshot: Record<string, number> | null
  sale_days_snapshot: Record<string, number> | null
  calculation_inputs_snapshot: CalculationInputsSnapshot | null
  calculation_warnings: Array<{
    code: string
    country: string
    reason: string | null
    message: string
  }>
  urgent: boolean
  purchase_qty: number
  procurement_export_status: 'pending' | 'exported'
  procurement_exported_snapshot_id: number | null
  procurement_exported_at: string | null
  restock_export_status: 'pending' | 'exported'
  restock_exported_snapshot_id: number | null
  restock_exported_at: string | null
}

export interface SuggestionDetail extends Suggestion {
  items: SuggestionItem[]
}

export interface SuggestionItemPatch {
  total_qty?: number
  purchase_qty?: number
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
  patch: SuggestionItemPatch,
): Promise<SuggestionItem> {
  const { data } = await client.patch<SuggestionItem>(
    `/api/suggestions/${suggestionId}/items/${itemId}`,
    patch,
  )
  return data
}

export async function recalculateSuggestionItem(
  suggestionId: number,
  itemId: number,
): Promise<SuggestionItem> {
  const { data } = await client.post<SuggestionItem>(
    `/api/suggestions/${suggestionId}/items/${itemId}/recalculate`,
  )
  return data
}

export async function deleteSuggestion(suggestionId: number): Promise<void> {
  await client.delete(`/api/suggestions/${suggestionId}`)
}
