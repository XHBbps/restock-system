<template>
  <div class="detail-view">
    <PageSectionCard v-if="suggestion" title="建议单详情">
      <template #actions>
        <el-tag :type="suggestionStatusMeta.tagType">
          {{ suggestionStatusMeta.label }}
        </el-tag>
        <span class="summary-chip">#{{ suggestion.id }}</span>
        <span class="summary-chip">创建：{{ formatDateTime(suggestion.created_at) }}</span>
        <el-button @click="goBack">返回</el-button>
      </template>

      <SuggestionTabBar :base-path="`/restock/suggestions/${suggestion.id}`" />
      <router-view v-slot="{ Component }">
        <component
          :is="Component"
          :suggestion="suggestion"
          :items="suggestion.items"
          :loading="loading"
          @refresh="load"
        />
      </router-view>
    </PageSectionCard>

    <el-empty v-else-if="notFound" description="建议单不存在或已失效。" :image-size="84">
      <el-button type="primary" @click="goCurrent">返回当前建议</el-button>
    </el-empty>

    <el-empty v-else-if="loadError" :description="loadError" :image-size="84">
      <el-button type="primary" @click="load">重新加载</el-button>
    </el-empty>

    <div v-else class="loading">加载中...</div>
  </div>
</template>

<script setup lang="ts">
import { getSuggestion, type SuggestionDetail } from '@/api/suggestion'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SuggestionTabBar from '@/components/SuggestionTabBar.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { getSuggestionDisplayStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { computed, watch } from 'vue'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const suggestion = ref<SuggestionDetail | null>(null)
const loading = ref(false)
const notFound = ref(false)
const loadError = ref('')

const totalSnapshotCount = computed(
  () =>
    (suggestion.value?.procurement_snapshot_count ?? 0) +
    (suggestion.value?.restock_snapshot_count ?? 0),
)

const suggestionStatusMeta = computed(() =>
  suggestion.value
    ? getSuggestionDisplayStatusMeta(suggestion.value.status, totalSnapshotCount.value)
    : { label: '暂无', tagType: 'info' as const },
)

function formatDateTime(value?: string | null): string {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'
}

function parsePositiveInt(value: unknown): number | null {
  const raw = Array.isArray(value) ? value[0] : value
  const parsed = Number(raw)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

async function load(): Promise<void> {
  const id = parsePositiveInt(route.params.id)
  if (!id) {
    notFound.value = true
    suggestion.value = null
    return
  }

  loading.value = true
  notFound.value = false
  loadError.value = ''
  try {
    suggestion.value = await getSuggestion(id)
  } catch (error) {
    suggestion.value = null
    const status = (error as { response?: { status?: number } })?.response?.status
    if (status === 404) {
      notFound.value = true
    } else {
      loadError.value = getActionErrorMessage(error, '加载建议详情失败')
    }
  } finally {
    loading.value = false
  }
}

function goBack(): void {
  if (typeof window !== 'undefined' && window.history.length > 1) {
    router.back()
    return
  }
  router.push('/restock/current')
}

function goCurrent(): void {
  router.push('/restock/current')
}

watch(
  () => route.params.id,
  () => {
    void load()
  },
  { immediate: true },
)
</script>

<style lang="scss" scoped>
.detail-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.summary-chip {
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.loading {
  text-align: center;
  padding: $space-12;
  color: $color-text-secondary;
}
</style>
