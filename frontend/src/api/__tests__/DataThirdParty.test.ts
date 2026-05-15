import { afterEach, describe, expect, it, vi } from 'vitest'

import client from '../client'
import {
  confirmThirdPartyInventoryImport,
  createThirdPartyWarehouse,
  deleteThirdPartyInventoryItem,
  listThirdPartyInventoryWarehouseGroups,
  listThirdPartyWarehouses,
  previewThirdPartyInventoryImport,
  updateThirdPartyInventoryItem,
} from '../data'

describe('api/data third-party inventory', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('lists third-party warehouses with filters', async () => {
    const get = vi.spyOn(client, 'get').mockResolvedValue({
      data: { items: [], total: 0, page: 1, pageSize: 20 },
    })

    await listThirdPartyWarehouses({ keyword: 'US', only_missing_country: true })

    expect(get).toHaveBeenCalledWith('/api/data/third-party-warehouses', {
      params: { keyword: 'US', only_missing_country: true },
    })
  })

  it('creates third-party warehouse', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: { id: 1, name: 'US 3PL', country: null },
    })

    await createThirdPartyWarehouse({ name: 'US 3PL', country: null })

    expect(post).toHaveBeenCalledWith('/api/data/third-party-warehouses', {
      name: 'US 3PL',
      country: null,
    })
  })

  it('previews import with filename header', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({
      data: { id: 1, newWarehouses: [], unmaintainedWarehouses: [], issues: [] },
    })
    const file = new File(['x'], '库存.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })

    await previewThirdPartyInventoryImport(file)

    expect(post).toHaveBeenCalledWith(
      '/api/data/third-party-inventory/import/preview',
      file,
      {
        headers: {
          'Content-Type': file.type,
          'X-Filename': encodeURIComponent(file.name),
        },
      },
    )
  })

  it('confirms import and lists current groups', async () => {
    const post = vi.spyOn(client, 'post').mockResolvedValue({ data: { id: 7, status: 'applied' } })
    const get = vi.spyOn(client, 'get').mockResolvedValue({
      data: { items: [], total: 0, page: 1, pageSize: 20 },
    })

    await confirmThirdPartyInventoryImport(7)
    await listThirdPartyInventoryWarehouseGroups({ only_participating: true, only_nonzero: true })

    expect(post).toHaveBeenCalledWith('/api/data/third-party-inventory/import/7/confirm')
    expect(get).toHaveBeenCalledWith('/api/data/third-party-inventory/warehouse-groups', {
      params: { only_participating: true, only_nonzero: true },
    })
  })

  it('updates and deletes current inventory items', async () => {
    const patch = vi.spyOn(client, 'patch').mockResolvedValue({ data: { id: 5 } })
    const del = vi.spyOn(client, 'delete').mockResolvedValue({})

    await updateThirdPartyInventoryItem(5, { available: 10, reserved: 1 })
    await deleteThirdPartyInventoryItem(5)

    expect(patch).toHaveBeenCalledWith('/api/data/third-party-inventory/items/5', {
      available: 10,
      reserved: 1,
    })
    expect(del).toHaveBeenCalledWith('/api/data/third-party-inventory/items/5')
  })
})
