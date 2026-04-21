<template>
  <RestockListView
    :suggestion="suggestion"
    :items="items"
    :loading="loading"
    @refresh="$emit('refresh')"
  />
</template>

<script setup lang="ts">
import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'
import RestockListView from './RestockListView.vue'

defineProps<{
  suggestion: SuggestionDetail | null
  items: SuggestionItem[]
  loading?: boolean
}>()

defineEmits<{
  refresh: []
}>()
</script>
