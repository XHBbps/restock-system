import { describe, expect, it } from 'vitest'

import { syncJobLabelMap } from '../sync'

describe('syncJobLabelMap', () => {
  it('keeps manual calc_engine out of sync log labels', () => {
    expect(syncJobLabelMap).not.toHaveProperty('calc_engine')
  })

  it('includes background task labels shown in sync log', () => {
    expect(syncJobLabelMap).toHaveProperty('daily_archive', '每日归档')
    expect(syncJobLabelMap).toHaveProperty('retry_failed_api_calls', '失败调用重试')
  })
})
