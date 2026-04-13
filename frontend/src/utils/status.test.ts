import { describe, expect, it } from 'vitest'

import { getListingOnlineStatusMeta, getOutRecordTransitStatusMeta, getSuggestionPushStatusMeta } from './status'

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

describe('getOutRecordTransitStatusMeta', () => {
  it('maps active in-transit rows to 在途', () => {
    expect(getOutRecordTransitStatusMeta(true)).toEqual({
      label: '在途',
      tagType: 'success',
    })
  })

  it('maps inactive rows to 完结', () => {
    expect(getOutRecordTransitStatusMeta(false)).toEqual({
      label: '完结',
      tagType: 'info',
    })
  })
})

describe('getSuggestionPushStatusMeta', () => {
  it('maps blocked rows to the same display meta as pending', () => {
    expect(getSuggestionPushStatusMeta('blocked')).toEqual({
      label: '待推送',
      tagType: 'warning',
    })
  })
})
