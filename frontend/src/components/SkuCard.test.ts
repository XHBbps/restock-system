// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SkuCard from './SkuCard.vue'

describe('SkuCard', () => {
  it('shows the no-image placeholder when no image is provided', () => {
    const wrapper = mount(SkuCard, {
      props: {
        sku: 'SKU-1',
        name: 'Product',
      },
      global: {
        stubs: {
          ElTag: true,
        },
      },
    })

    expect(wrapper.find('img.sku-image').exists()).toBe(false)
    expect(wrapper.find('.sku-image-placeholder').text()).toBe('无图')
  })

  it('falls back to the no-image placeholder when the image fails to load', async () => {
    const wrapper = mount(SkuCard, {
      props: {
        sku: 'SKU-1',
        name: 'Product',
        image: 'https://example.test/missing.png',
      },
      global: {
        stubs: {
          ElTag: true,
        },
      },
    })

    expect(wrapper.find('img.sku-image').exists()).toBe(true)

    await wrapper.find('img.sku-image').trigger('error')

    expect(wrapper.find('img.sku-image').exists()).toBe(false)
    expect(wrapper.find('.sku-image-placeholder').text()).toBe('无图')
  })

  it('tries the new image URL after the image prop changes', async () => {
    const wrapper = mount(SkuCard, {
      props: {
        sku: 'SKU-1',
        image: 'https://example.test/missing.png',
      },
      global: {
        stubs: {
          ElTag: true,
        },
      },
    })

    await wrapper.find('img.sku-image').trigger('error')
    expect(wrapper.find('.sku-image-placeholder').exists()).toBe(true)

    await wrapper.setProps({ image: 'https://example.test/ok.png' })

    expect(wrapper.find('img.sku-image').exists()).toBe(true)
    expect(wrapper.find('img.sku-image').attributes('src')).toBe('https://example.test/ok.png')
  })
})
