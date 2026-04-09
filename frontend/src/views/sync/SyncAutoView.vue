<template>
  <div class="sync-auto-view">
    <el-alert
      type="info"
      :closable="false"
      title="当前阶段先提供自动同步看板，展示建议频率和最近执行状态；若后端补齐调度控制接口，可在此页继续接入开关与计划编辑。"
    />

    <section class="intro-card">
      <div>
        <h1 class="page-title">自动同步</h1>
        <p class="page-desc">
          自动同步页负责说明建议执行频率和最近运行结果，帮助判断哪些任务应纳入调度器统一托管。
        </p>
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
          <div class="job-card__desc">{{ job.description }}</div>
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

.page-desc {
  margin: $space-2 0 0;
  color: $color-text-secondary;
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

.job-card__desc,
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
