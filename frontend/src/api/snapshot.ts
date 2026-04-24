import client from './client'

export type SnapshotType = 'procurement' | 'restock'

export interface SnapshotOut {
  id: number
  suggestion_id: number
  snapshot_type: SnapshotType
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
  restock_dates: Record<string, string | null>
  purchase_qty: number | null
  urgent: boolean
  velocity_snapshot: Record<string, unknown> | null
  sale_days_snapshot: Record<string, unknown> | null
}

export interface SnapshotDetailOut extends SnapshotOut {
  items: SnapshotItemOut[]
  global_config_snapshot: Record<string, unknown>
}

async function createTypedSnapshot(
  suggestionId: number,
  type: SnapshotType,
  itemIds: number[],
  note?: string,
): Promise<SnapshotOut> {
  const { data } = await client.post<SnapshotOut>(
    `/api/suggestions/${suggestionId}/snapshots/${type}`,
    { item_ids: itemIds, note },
  )
  return data
}

export function createProcurementSnapshot(
  suggestionId: number,
  itemIds: number[],
  note?: string,
): Promise<SnapshotOut> {
  return createTypedSnapshot(suggestionId, 'procurement', itemIds, note)
}

export function createRestockSnapshot(
  suggestionId: number,
  itemIds: number[],
  note?: string,
): Promise<SnapshotOut> {
  return createTypedSnapshot(suggestionId, 'restock', itemIds, note)
}

export async function listSnapshots(
  suggestionId: number,
  type?: SnapshotType,
): Promise<SnapshotOut[]> {
  const { data } = await client.get<SnapshotOut[]>(
    `/api/suggestions/${suggestionId}/snapshots`,
    { params: type ? { type } : undefined },
  )
  return data
}

export async function getSnapshot(snapshotId: number): Promise<SnapshotDetailOut> {
  const { data } = await client.get<SnapshotDetailOut>(`/api/snapshots/${snapshotId}`)
  return data
}

export async function downloadSnapshotBlob(
  snapshotId: number,
): Promise<{ blob: Blob; filename: string }> {
  try {
    const resp = await client.get(`/api/snapshots/${snapshotId}/download`, {
      responseType: 'blob',
    })
    const disposition = (resp.headers['content-disposition'] as string | undefined) || ''
    const match = disposition.match(/filename\*?=(?:UTF-8'')?["]?([^;"\r\n]+)["]?/i)
    const filename = match ? decodeURIComponent(match[1]) : `snapshot-${snapshotId}.xlsx`
    return { blob: resp.data as Blob, filename }
  } catch (error) {
    // responseType:'blob' 让 4xx/5xx 的 JSON body 也被包成 Blob，
    // getActionErrorMessage 看不到 detail。解包成 JSON 再抛，保证友好提示
    // （如 "该版本已过期清理" 410 Gone）。
    await _decodeBlobErrorInPlace(error)
    throw error
  }
}

async function _decodeBlobErrorInPlace(error: unknown): Promise<void> {
  const maybe = error as { response?: { data?: unknown } }
  const data = maybe.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      if (text.trim()) {
        maybe.response!.data = JSON.parse(text)
      }
    } catch {
      // 保留原始 blob；getActionErrorMessage 会 fallback 到 "下载失败"
    }
  }
}
