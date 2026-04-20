import { describe, expect, it } from 'vitest'

import {
  deriveSuggestionDisplayStatus,
  getListingOnlineStatusMeta,
  getOutRecordTransitStatusMeta,
  getSuggestionDisplayStatusMeta,
} from './status'

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

describe('deriveSuggestionDisplayStatus', () => {
  it('draft without snapshot → pending', () => {
    expect(deriveSuggestionDisplayStatus('draft', 0)).toBe('pending')
  })

  it('draft with snapshots → exported', () => {
    expect(deriveSuggestionDisplayStatus('draft', 1)).toBe('exported')
    expect(deriveSuggestionDisplayStatus('draft', 5)).toBe('exported')
  })

  it('archived → archived regardless of snapshot_count', () => {
    expect(deriveSuggestionDisplayStatus('archived', 0)).toBe('archived')
    expect(deriveSuggestionDisplayStatus('archived', 3)).toBe('archived')
  })

  it('error → error regardless of snapshot_count', () => {
    expect(deriveSuggestionDisplayStatus('error', 0)).toBe('error')
    expect(deriveSuggestionDisplayStatus('error', 2)).toBe('error')
  })
})

describe('getSuggestionDisplayStatusMeta', () => {
  it('maps 4 display states to 中文 labels', () => {
    expect(getSuggestionDisplayStatusMeta('draft', 0)).toEqual({
      label: '未提交',
      tagType: 'warning',
    })
    expect(getSuggestionDisplayStatusMeta('draft', 2)).toEqual({
      label: '已导出',
      tagType: 'success',
    })
    expect(getSuggestionDisplayStatusMeta('archived', 0)).toEqual({
      label: '已归档',
      tagType: 'info',
    })
    expect(getSuggestionDisplayStatusMeta('error', 0)).toEqual({
      label: '异常',
      tagType: 'danger',
    })
  })
})
