import { describe, expect, it } from 'vitest'

import { getCountryLabel } from './countries'

describe('countries', () => {
  it('formats newly observed country codes with Chinese labels', () => {
    expect(getCountryLabel('AT')).toBe('AT - 奥地利')
    expect(getCountryLabel('CH')).toBe('CH - 瑞士')
    expect(getCountryLabel('CY')).toBe('CY - 塞浦路斯')
    expect(getCountryLabel('DK')).toBe('DK - 丹麦')
    expect(getCountryLabel('EE')).toBe('EE - 爱沙尼亚')
    expect(getCountryLabel('FI')).toBe('FI - 芬兰')
    expect(getCountryLabel('LT')).toBe('LT - 立陶宛')
    expect(getCountryLabel('LV')).toBe('LV - 拉脱维亚')
    expect(getCountryLabel('MT')).toBe('MT - 马耳他')
    expect(getCountryLabel('SI')).toBe('SI - 斯洛文尼亚')
  })
})
