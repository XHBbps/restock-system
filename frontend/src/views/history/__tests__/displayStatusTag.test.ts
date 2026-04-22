import { describe, expect, it } from 'vitest'

import type { SuggestionDisplayStatusCode } from '@/api/suggestion'
import { STATUS_TAG_MAP, statusTagType } from '@/views/history/displayStatusTag'

describe('displayStatusTag.statusTagType', () => {
  it('maps each known code to expected Element Plus tag type', () => {
    const cases: Array<{
      code: SuggestionDisplayStatusCode
      expected: 'success' | 'warning' | 'info' | 'danger'
    }> = [
      { code: 'exported', expected: 'success' },
      { code: 'pending', expected: 'warning' },
      { code: 'archived', expected: 'info' },
      { code: 'error', expected: 'danger' },
    ]
    for (const { code, expected } of cases) {
      expect(statusTagType(code)).toBe(expected)
    }
  })

  it('covers every SuggestionDisplayStatusCode enum value in STATUS_TAG_MAP', () => {
    // 防止新增 code 时 STATUS_TAG_MAP 漏补映射
    const codes: SuggestionDisplayStatusCode[] = ['pending', 'exported', 'archived', 'error']
    for (const code of codes) {
      expect(STATUS_TAG_MAP[code]).toBeDefined()
    }
  })

  it('falls back to info for unknown codes', () => {
    // 模拟后端返回未在枚举内的 code；类型断言绕过编译期检查
    const unknown = 'void' as unknown as SuggestionDisplayStatusCode
    expect(statusTagType(unknown)).toBe('info')
  })
})
