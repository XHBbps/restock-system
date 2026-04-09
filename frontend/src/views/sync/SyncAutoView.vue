<template>
  <div class="sync-auto-view">
    <section class="intro-card">
      <div>
        <h1 class="page-title">自动同步</h1>
      </div>
      <el-button @click="reload">刷新看板</el-button>
    </section>

    <section class="card-grid">
      <el-card v-for="job in jobs" :key="job.jobName" shadow="never">
        <div class="job-card">
          <div class="job-card__top">
            <div class="job-card__title">{{ job.label }}</div>
            <el-tag :type="job.status.tagType">{{ job.status.label }}</el-tag>
          </div>
          <div class="job-card__cadence">{{ job.cadence }}</div>
          <div class="job-card__meta">
            <div>最近运行：{{ job.lastRunAt }}</div>
            <div>最近成功：{{ job.lastSuccessAt }}</div>
            <div v-if="job.lastError" class="job-card__error">最近错误：{{ job.lastError }}</div>
          </div>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup lang="ts">
import { listSyncState, type SyncStateRow } from '@/api/data'
import { autoSyncDefinitions } from '@/config/sync'
import { getSyncStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { computed, onMounted, ref } from 'vue'

const syncState = ref<SyncStateRow[]>([])

function formatTime(value?: string | null): string {
  return value ? dayjs(value).format('MM-DD HH:mm:ss') : '暂无记录'
}

const jobs = computed(() =>
  autoSyncDefinitions.map((definition) => {
    const row = syncState.value.find((item) => item.job_name === definition.jobName)
    return {
      ...definition,
      status: getSyncStatusMeta(row?.last_status),
      lastRunAt: formatTime(row?.last_run_at),
      lastSuccessAt: formatTime(row?.last_success_at),
      lastError: row?.last_error || '',
    }
  }),
)

async function reload(): Promise<void> {
  syncState.value = await listSyncState()
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.sync-auto-view {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.intro-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $space-4;
  padding: $space-5;
  border-radius: $radius-xl;
  border: 1px solid $color-border-default;
  background: $color-bg-card;
}

.page-title {
  margin: 0;
  font-size: 24px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: $space-4;
}

.job-card {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.job-card__top {
  display: flex;
  justify-content: space-between;
  gap: $space-3;
}

.job-card__title {
  font-weight: $font-weight-semibold;
  font-size: $font-size-lg;
}

.job-card__meta {
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.job-card__cadence {
  padding: $space-2 $space-3;
  border-radius: $radius-md;
  background: $color-bg-subtle;
  font-size: $font-size-sm;
}

.job-card__meta {
  display: flex;
  flex-direction: column;
  gap: $space-2;
}

.job-card__error {
  color: $color-danger;
}

@media (max-width: 900px) {
  .intro-card,
  .job-card__top {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
