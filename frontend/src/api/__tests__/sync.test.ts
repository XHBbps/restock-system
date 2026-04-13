import { afterEach, describe, expect, it, vi } from 'vitest'

import client from '../client'
import { refetchOrderDetail } from '../sync'

describe('api/sync', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('posts order-detail refetch payload', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: {
        task_id: 12,
        existing: false,
        matched_count: 20,
        queued_count: 20,
        truncated: false,
      },
    })

    const result = await refetchOrderDetail({
      days: 7,
      limit: 100,
      shop_id: 'shop-1',
    })

    expect(post).toHaveBeenCalledWith('/api/sync/order-detail/refetch', {
      days: 7,
      limit: 100,
      shop_id: 'shop-1',
    })
    expect(result.task_id).toBe(12)
    expect(result.queued_count).toBe(20)
  })
})
