// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'

function makeItem(id: number, overrides: Partial<SuggestionItem> = {}): SuggestionItem {
  return {
    id,
    commodity_sku: `SKU-${id}`,
    commodity_name: null,
    main_image: null,
    total_qty: 10,
    country_breakdown: { US: 10 },
    warehouse_breakdown: { US: { 'WH-1': 10 } },
    allocation_snapshot: null,
    velocity_snapshot: null,
    sale_days_snapshot: null,
    urgent: false,
    purchase_qty: 10,
    purchase_date: null,
    procurement_export_status: 'pending',
    procurement_exported_snapshot_id: null,
    procurement_exported_at: null,
    restock_export_status: 'pending',
    restock_exported_snapshot_id: null,
    restock_exported_at: null,
    ...overrides,
  }
}

function makeSuggestion(overrides: Partial<SuggestionDetail> = {}): SuggestionDetail {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 2,
    procurement_item_count: 1,
    restock_item_count: 1,
    procurement_snapshot_count: 0,
    restock_snapshot_count: 0,
    global_config_snapshot: {},
    created_at: '2026-04-21T10:00:00',
    archived_at: null,
    items: [],
    ...overrides,
  }
}

const STUBS = {
  ElEmpty: true,
  ElInput: true,
  ElButton: true,
  ElTable: { template: '<div><slot /></div>' },
  ElTableColumn: true,
  ElTag: { template: '<span><slot /></span>' },
  SkuCard: true,
}

describe('RestockListView', () => {
  it('renders only rows with positive country breakdown total', async () => {
    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: {
        suggestion: makeSuggestion(),
        items: [
          makeItem(1, { country_breakdown: { US: 10 } }),
          makeItem(2, { country_breakdown: { US: 0 } }),
        ],
      },
      global: { stubs: STUBS },
    })
    await flushPromises()

    const vm = wrapper.vm as unknown as { filteredItems: SuggestionItem[] }
    expect(vm.filteredItems.map((item) => item.id)).toEqual([1])
  })

  it('shows empty state when there is no restock demand', async () => {
    const { default: View } = await import('../RestockListView.vue')
    const wrapper = shallowMount(View, {
      props: { suggestion: makeSuggestion({ restock_item_count: 0 }), items: [] },
      global: { stubs: STUBS },
    })

    expect(wrapper.findComponent({ name: 'ElEmpty' }).exists()).toBe(true)
  })
})
