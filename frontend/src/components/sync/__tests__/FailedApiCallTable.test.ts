// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent, h, inject, provide } from 'vue'

import type { RecentCall } from '@/api/monitor'
import { useAuthStore, type UserInfo } from '@/stores/auth'
import FailedApiCallTable from '../FailedApiCallTable.vue'

const TableRowProvider = defineComponent({
  name: 'TableRowProvider',
  props: {
    row: {
      type: Object,
      required: true,
    },
  },
  setup(props, { slots }) {
    provide('tableRow', props.row)
    return () => h('div', { class: 'table-row-stub' }, slots.default?.())
  },
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        { class: 'el-table-stub' },
        props.data.map((row) =>
          h(TableRowProvider, { row: row as Record<string, unknown> }, { default: () => slots.default?.() }),
        ),
      )
  },
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  setup(_, { slots }) {
    const row = inject<Record<string, unknown>>('tableRow', {})
    return () => h('div', { class: 'el-table-column-stub' }, slots.default?.({ row }))
  },
})

const STUBS = {
  ElTable: ElTableStub,
  'el-table': ElTableStub,
  ElTableColumn: ElTableColumnStub,
  'el-table-column': ElTableColumnStub,
  ElTooltip: {
    props: ['disabled'],
    template: `
      <span class="tooltip-stub">
        <slot />
        <span v-if="!disabled" class="tooltip-content"><slot name="content" /></span>
      </span>
    `,
  },
  'el-tooltip': {
    props: ['disabled'],
    template: `
      <span class="tooltip-stub">
        <slot />
        <span v-if="!disabled" class="tooltip-content"><slot name="content" /></span>
      </span>
    `,
  },
  ElButton: {
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-button': {
    template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
  },
}

function makeRow(overrides: Partial<RecentCall> = {}): RecentCall {
  return {
    id: 1,
    endpoint: '/api/shop/pageList.json',
    called_at: '2026-05-03T12:00:00',
    duration_ms: 88,
    http_status: 200,
    saihu_code: 40019,
    saihu_msg: 'rate limited',
    error_type: 'rate_limit',
    retry_status: null,
    retry_display_status: 'not_queued',
    retry_display_text: '未入自动队列',
    retry_attempt_text: '-',
    auto_retry_attempts: 0,
    next_retry_at: null,
    resolved_at: null,
    last_retry_error: null,
    retry_source_log_id: null,
    has_request_payload: true,
    can_retry: true,
    ...overrides,
  }
}

function setUser(permissions: string[] = ['sync:operate']) {
  const user: UserInfo = {
    id: 1,
    username: 'owner',
    displayName: 'Owner',
    roleName: '管理员',
    isSuperadmin: false,
    passwordIsDefault: false,
    permissions,
  }
  useAuthStore().setAuth('token', user)
}

function mountTable(rows: RecentCall[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  setUser()
  return mount(FailedApiCallTable, {
    props: { rows },
    global: {
      plugins: [pinia],
      stubs: STUBS,
    },
  })
}

describe('FailedApiCallTable', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('does not render 0/5 for null retry status rows', () => {
    const wrapper = mountTable([makeRow()])

    expect(wrapper.text()).toContain('未入自动队列')
    expect(wrapper.text()).toContain('-')
    expect(wrapper.text()).not.toContain('0/5')
  })

  it('renders queued retry attempts and diagnostic tooltip content', () => {
    const wrapper = mountTable([
      makeRow({
        retry_status: 'queued',
        retry_display_status: 'queued',
        retry_display_text: '待自动重试',
        retry_attempt_text: '0/5',
        next_retry_at: '2026-05-03T12:05:00',
        last_retry_error: 'still limited',
      }),
    ])

    expect(wrapper.text()).toContain('待自动重试')
    expect(wrapper.text()).toContain('0/5')
    expect(wrapper.text()).toContain('下次重试：05-03 12:05:00')
    expect(wrapper.text()).toContain('最近错误：still limited')
  })
})
