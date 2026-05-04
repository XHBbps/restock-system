import { afterEach, describe, expect, it, vi } from 'vitest'

import client from '../client'
import { getSchedulerStatus, setSchedulerStatus } from '../sync'

describe('api/sync', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('fetches scheduler status', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({
      data: {
        enabled: true,
        running: true,
        timezone: 'Asia/Hong_Kong',
        sync_interval_minutes: 60,
        order_sync_interval_minutes: 120,
        calc_cron: '0 4 * * *',
        jobs: []
      }
    })

    const result = await getSchedulerStatus()

    expect(get).toHaveBeenCalledWith('/api/sync/scheduler')
    expect(result.enabled).toBe(true)
    expect(result.order_sync_interval_minutes).toBe(120)
  })

  it('posts scheduler toggle payload', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: {
        enabled: false,
        running: false,
        timezone: 'Asia/Hong_Kong',
        sync_interval_minutes: 60,
        order_sync_interval_minutes: 120,
        jobs: []
      }
    })

    const result = await setSchedulerStatus(false)

    expect(post).toHaveBeenCalledWith('/api/sync/scheduler', { enabled: false })
    expect(result.enabled).toBe(false)
  })
})
