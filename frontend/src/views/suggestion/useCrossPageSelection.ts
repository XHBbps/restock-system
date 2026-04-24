import { computed, ref, watch, type ComputedRef, type WatchSource } from 'vue'

interface UseCrossPageSelectionOptions {
  allSelectableIds: ComputedRef<number[]>
  resetKey: WatchSource<unknown>
}

export function useCrossPageSelection(options: UseCrossPageSelectionOptions) {
  const selectedIds = ref<number[]>([])
  const selectedIdSet = computed(() => new Set(selectedIds.value))

  const selectedCount = computed(() => selectedIds.value.length)
  const isAllSelected = computed(
    () =>
      options.allSelectableIds.value.length > 0 &&
      selectedIds.value.length === options.allSelectableIds.value.length,
  )
  const isIndeterminate = computed(
    () =>
      selectedIds.value.length > 0 &&
      selectedIds.value.length < options.allSelectableIds.value.length,
  )

  watch(options.resetKey, () => {
    selectedIds.value = []
  })

  watch(
    options.allSelectableIds,
    (allSelectableIds) => {
      const allowedIds = new Set(allSelectableIds)
      const nextSelectedIds = selectedIds.value.filter((id) => allowedIds.has(id))
      if (nextSelectedIds.length !== selectedIds.value.length) {
        selectedIds.value = nextSelectedIds
      }
    },
    { immediate: true },
  )

  function toggleSelectAll(checked: boolean): void {
    selectedIds.value = checked ? [...options.allSelectableIds.value] : []
  }

  function toggleRow(id: number, checked: boolean): void {
    if (!options.allSelectableIds.value.includes(id)) return

    if (checked) {
      if (!selectedIdSet.value.has(id)) {
        selectedIds.value = [...selectedIds.value, id]
      }
      return
    }

    if (selectedIdSet.value.has(id)) {
      selectedIds.value = selectedIds.value.filter((selectedId) => selectedId !== id)
    }
  }

  function isRowSelected(id: number): boolean {
    return selectedIdSet.value.has(id)
  }

  return {
    selectedIds,
    selectedCount,
    isAllSelected,
    isIndeterminate,
    toggleSelectAll,
    toggleRow,
    isRowSelected,
  }
}
