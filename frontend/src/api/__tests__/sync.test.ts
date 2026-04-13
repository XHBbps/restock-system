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
        active_job_name: null,
        active_trigger_source: null,
        matched_count: 20,
        queued_count: 20,
        truncated: false,
      },
    })

    const result = await refetchOrderDetail({
      days: 7,
    })

    expect(post).toHaveBeenCalledWith('/api/sync/order-detail/refetch', {
      days: 7,
    })
    expect(result.task_id).toBe(12)
    expect(result.queued_count).toBe(20)
  })
})
