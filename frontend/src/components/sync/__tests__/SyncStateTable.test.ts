// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent, h, inject, provide } from 'vue'

import SyncStateTable from '../SyncStateTable.vue'

const TableRowProvider = defineComponent({
  name: 'TableRowProvider',
  props: {
    row: {
      type: Object,
      required: true
    }
  },
  setup(props, { slots }) {
    provide('tableRow', props.row)
    return () => h('div', { class: 'table-row-stub' }, slots.default?.())
  }
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: {
    data: {
      type: Array,
      default: () => []
    }
  },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { class: 'el-table-stub' },
        props.data.map((row) =>
          h(
            TableRowProvider,
            { row: row as Record<string, unknown> },
            { default: () => slots.default?.() }
          )
        )
      )
  }
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  setup(_, { slots }) {
    const row = inject<Record<string, unknown>>('tableRow', {})
    return () => h('div', { class: 'el-table-column-stub' }, slots.default?.({ row }))
  }
})

const STUBS = {
  ElTable: ElTableStub,
  'el-table': ElTableStub,
  ElTableColumn: ElTableColumnStub,
  'el-table-column': ElTableColumnStub,
  StatusTag: {
    props: ['meta'],
    template: '<span>{{ meta.label }}</span>'
  }
}

describe('SyncStateTable', () => {
  it('renders daily archive task-run success time', () => {
    const wrapper = mount(SyncStateTable, {
      props: {
        rows: [
          {
            job_name: 'daily_archive',
            last_run_at: '2026-05-04T02:00:00+08:00',
            last_success_at: '2026-05-04T02:03:00+08:00',
            last_status: 'success',
            last_error: null
          }
        ],
        jobLabelMap: {
          daily_archive: '每日归档'
        }
      },
      global: {
        stubs: STUBS
      }
    })

    expect(wrapper.text()).toContain('每日归档')
    expect(wrapper.text()).toContain('05-04 02:03:00')
    expect(wrapper.text()).not.toContain('暂无记录')
  })
})
