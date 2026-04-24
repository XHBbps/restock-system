<template>
  <div class="suggestion-tab-bar">
    <el-radio-group
      :model-value="activeTab"
      class="segmented-radio-group"
      @change="onChange"
    >
      <el-radio-button value="procurement">采购建议</el-radio-button>
      <el-radio-button value="restock">补货建议</el-radio-button>
    </el-radio-group>
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

const activeTab = computed<TabValue>(() =>
  route.path.endsWith('/restock') ? 'restock' : 'procurement',
)

const basePath = computed(() => {
  if (props.basePath) return props.basePath.replace(/\/$/, '')
  return route.path.replace(/\/(procurement|restock)$/, '')
})

function onChange(value: string | number | boolean | undefined): void {
  if (value !== 'procurement' && value !== 'restock') return
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
