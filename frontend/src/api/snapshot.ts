// 快照 API 客户端
import client from './client'

export interface SnapshotOut {
  id: number
  suggestion_id: number
  version: number
  note: string | null
  exported_by: number | null
  exported_by_name: string | null
  exported_at: string
  item_count: number
  generation_status: 'generating' | 'ready' | 'failed'
  file_size_bytes: number | null
  download_count: number
}

export interface SnapshotItemOut {
  id: number
  commodity_sku: string
  commodity_name: string | null
  main_image_url: string | null
  total_qty: number
  country_breakdown: Record<string, unknown>
  warehouse_breakdown: Record<string, unknown>
  urgent: boolean
  velocity_snapshot: Record<string, unknown> | null
  sale_days_snapshot: Record<string, unknown> | null
}

export interface SnapshotDetailOut extends SnapshotOut {
  items: SnapshotItemOut[]
  global_config_snapshot: Record<string, unknown>
}

export async function createSnapshot(
  suggestionId: number,
  itemIds: number[],
  note?: string,
): Promise<SnapshotOut> {
  const { data } = await client.post<SnapshotOut>(
    `/api/suggestions/${suggestionId}/snapshots`,
    { item_ids: itemIds, note },
  )
  return data
}

export async function listSnapshots(suggestionId: number): Promise<SnapshotOut[]> {
  // 后端按 version asc 返回，前端 reverse 让最新版本在表格顶部
  const { data } = await client.get<SnapshotOut[]>(
    `/api/suggestions/${suggestionId}/snapshots`,
  )
  return [...data].reverse()
}

export async function getSnapshot(snapshotId: number): Promise<SnapshotDetailOut> {
  const { data } = await client.get<SnapshotDetailOut>(`/api/snapshots/${snapshotId}`)
  return data
}

export async function downloadSnapshotBlob(
  snapshotId: number,
): Promise<{ blob: Blob; filename: string }> {
  const resp = await client.get(`/api/snapshots/${snapshotId}/download`, {
    responseType: 'blob',
  })
  const disposition = (resp.headers['content-disposition'] as string | undefined) || ''
  const match = disposition.match(/filename\*?=(?:UTF-8'')?["]?([^;"\r\n]+)["]?/i)
  const filename = match ? decodeURIComponent(match[1]) : `snapshot-${snapshotId}.xlsx`
  return { blob: resp.data as Blob, filename }
}
