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

  it('renders DatePicker in editable mode and keeps level class', () => {
    const date = dayjs().subtract(3, 'day').format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, {
      props: { date, editable: true },
      global: {
        stubs: {
          ElTag: { template: '<span class="tag-stub"><slot /></span>' },
          ElDatePicker: { template: '<input class="picker-stub" />' },
        },
      },
    })
    // 编辑模式下 class 仍按紧急度分档
    expect(wrapper.classes()).toContain('is-overdue')
    // 渲染 DatePicker stub 而非纯文本
    expect(wrapper.find('.picker-stub').exists()).toBe(true)
    // 徽章仍然显示
    expect(wrapper.text()).toContain('逾期 3 天')
  })

  it('editable mode hides loose note (只读才显示)', () => {
    const date = dayjs().add(60, 'day').format('YYYY-MM-DD')
    const wrapper = mount(PurchaseDateCell, {
      props: { date, editable: true },
      global: {
        stubs: {
          ElDatePicker: { template: '<input class="picker-stub" />' },
        },
      },
    })
    expect(wrapper.classes()).toContain('is-loose')
    expect(wrapper.text()).not.toContain('宽松')
  })

  it('emits update:date when DatePicker changes', async () => {
    const wrapper = mount(PurchaseDateCell, {
      props: { date: '2026-05-01', editable: true },
      global: {
        stubs: {
          ElDatePicker: {
            template: '<input class="picker-stub" @click="$emit(\'update:modelValue\', \'2026-06-01\')" />',
            emits: ['update:modelValue'],
          },
        },
      },
    })
    await wrapper.find('.picker-stub').trigger('click')
    expect(wrapper.emitted('update:date')).toBeTruthy()
    expect(wrapper.emitted('update:date')?.[0]).toEqual(['2026-06-01'])
  })
})
