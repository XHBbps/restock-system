<template>
  <div class="suggestion-tab-bar">
    <el-segmented
      :model-value="activeTab"
      :options="options"
      @change="onChange"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type TabValue = 'procurement' | 'restock'

const props = defineProps<{
  basePath?: string
}>()

const route = useRoute()
const router = useRouter()

const options = [
  { label: '采购建议', value: 'procurement' },
  { label: '补货建议', value: 'restock' },
]

const activeTab = computed<TabValue>(() =>
  route.path.endsWith('/restock') ? 'restock' : 'procurement',
)

const basePath = computed(() => {
  if (props.basePath) return props.basePath.replace(/\/$/, '')
  return route.path.replace(/\/(procurement|restock)$/, '')
})

function onChange(value: string | number | boolean): void {
  router.push(`${basePath.value}/${value}`)
}
</script>

<style scoped lang="scss">
.suggestion-tab-bar {
  display: flex;
  justify-content: flex-start;
  margin-bottom: $space-4;
}
</style>
