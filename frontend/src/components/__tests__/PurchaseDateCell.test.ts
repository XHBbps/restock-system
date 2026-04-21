// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import PurchaseDateCell from '../PurchaseDateCell.vue'

describe('PurchaseDateCell', () => {
  it('renders empty state', () => {
    const wrapper = mount(PurchaseDateCell, { props: { date: null } })
    expect(wrapper.text()).toContain('—')
  })

  it('renders normal future date', () => {
    const date = dayjs().add(14, 'day').format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, { props: { date } })
    expect(wrapper.classes()).toContain('is-normal')
  })

  it('renders warning date within 7 days', () => {
    const date = dayjs().add(3, 'day').format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, { props: { date } })
    expect(wrapper.classes()).toContain('is-warning')
  })

  it('renders today badge', () => {
    const date = dayjs().format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, {
      props: { date },
      global: { stubs: { ElTag: { template: '<span><slot /></span>' } } },
    })
    expect(wrapper.text()).toContain('今日到期')
  })

  it('renders overdue badge', () => {
    const date = dayjs().subtract(2, 'day').format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, {
      props: { date },
      global: { stubs: { ElTag: { template: '<span><slot /></span>' } } },
    })
    expect(wrapper.text()).toContain('逾期 2 天')
  })

  it('renders loose note for 31-90 days', () => {
    const date = dayjs().add(60, 'day').format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, { props: { date } })
    expect(wrapper.classes()).toContain('is-loose')
    expect(wrapper.text()).toContain('宽松')
  })

  it('renders not-urgent badge for > 90 days', () => {
    const date = dayjs().add(200, 'day').format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, {
      props: { date },
      global: { stubs: { ElTag: { template: '<span><slot /></span>' } } },
    })
    expect(wrapper.classes()).toContain('is-not-urgent')
    expect(wrapper.text()).toContain('不紧急')
  })
})
