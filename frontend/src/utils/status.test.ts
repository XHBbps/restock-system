import { describe, expect, it } from 'vitest'

import { getListingOnlineStatusMeta } from './status'

describe('getListingOnlineStatusMeta', () => {
  it('treats active status case-insensitively as on sale', () => {
    expect(getListingOnlineStatusMeta('Active')).toEqual({
      label: '在售',
      tagType: 'success',
    })
    expect(getListingOnlineStatusMeta(' active ')).toEqual({
      label: '在售',
      tagType: 'success',
    })
  })

  it('treats non-active statuses as off sale', () => {
    expect(getListingOnlineStatusMeta('inActive')).toEqual({
      label: '不在售',
      tagType: 'info',
    })
    expect(getListingOnlineStatusMeta('offline')).toEqual({
      label: '不在售',
      tagType: 'info',
    })
  })

  it('falls back to unknown when status is empty', () => {
    expect(getListingOnlineStatusMeta('')).toEqual({
      label: '未知',
      tagType: 'info',
    })
    expect(getListingOnlineStatusMeta(undefined)).toEqual({
      label: '未知',
      tagType: 'info',
    })
  })
})
