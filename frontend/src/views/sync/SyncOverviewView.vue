<template>
  <div class="sync-overview-view">
    <section class="intro-card">
      <div>
        <h1 class="page-title">同步总览</h1>
        <p class="page-desc">
          这里汇总最近同步结果、核心任务状态和接口异常，用于判断当前是否需要进入手动同步或排障页面。
        </p>
      </div>
      <el-button @click="reloadAll">刷新总览</el-button>
    </section>

    <section class="metric-grid">
      <el-card v-for="metric in metrics" :key="metric.label" shadow="never">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value">{{ metric.value }}</div>
        <div class="metric-hint">{{ metric.hint }}</div>
      </el-card>
    </section>

    <section class="content-grid">
      <el-card shadow="never">
        <template #header>
          <span>核心任务状态</span>
        </template>
        <div class="job-list">
          <div v-for="job in keyJobs" :key="job.jobName" class="job-item">
            <div>
              <div class="job-title">{{ job.label }}</div>
            </div>
            <div class="job-right">
              <el-tag :type="job.status.tagType">{{ job.status.label }}</el-tag>
              <span class="job-time">{{ job.lastRunAt }}</span>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <span>自动同步看板</span>
        </template>
        <div class="job-list">
          <div v-for="job in autoJobs" :key="job.jobName" class="job-item">
            <div>
              <div class="job-title">{{ job.label }}</div>
              <div class="job-meta">{{ job.cadence }}</div>
            </div>
            <div class="job-right">
              <el-tag :type="job.status.tagType">{{ job.status.label }}</el-tag>
              <span class="job-time">{{ job.lastSuccessAt }}</span>
            </div>
          </div>
        </div>
      </el-card>
    </section>

    <el-card shadow="never">
      <template #header>
        <span>最近失败调用</span>
      </template>
      <el-table :data="failedCalls" empty-text="最近 24 小时没有失败调用">
        <el-table-column label="调用时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.called_at) }}</template>
        </el-table-column>
        <el-table-column label="接口名称" min-width="220">
          <template #default="{ row }">{{ row.endpoint }}</template>
        </el-table-column>
        <el-table-column label="HTTP 状态" prop="http_status" width="100" align="center" />
        <el-table-column label="赛狐返回码" prop="saihu_code" width="120" align="center" />
        <el-table-column label="错误信息" min-width="260">
          <template #default="{ row }">{{ row.saihu_msg || row.error_type || '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { listSyncState, type SyncStateRow } from '@/api/data'
import { getApiCallsOverview, getRecentCalls, type RecentCall } from '@/api/monitor'
import { autoSyncDefinitions } from '@/config/sync'
import { getSyncStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { computed, onMounted, ref } from 'vue'

interface JobViewModel {
  jobName: string
  label: string
  cadence?: string
  status: ReturnType<typeof getSyncStatusMeta>
  lastRunAt: string
  lastSuccessAt: string
}

const syncState = ref<SyncStateRow[]>([])
const failedCalls = ref<RecentCall[]>([])
const failedApiCount = ref(0)

const keyJobDefinitions = [
  {
    jobName: 'sync_all',
    label: '全量同步',
  },
  {
    jobName: 'sync_inventory',
    label: '库存同步',
  },
  {
    jobName: 'sync_order_list',
    label: '订单列表同步',
  },
  {
    jobName: 'sync_product_listing',
    label: '商品同步',
  },
]

const metrics = computed(() => [
  {
    label: '已纳入任务',
    value: syncState.value.length,
    hint: '同步看板中的任务总数',
  },
  {
    label: '执行中任务',
    value: syncState.value.filter((item) => item.last_status === 'running').length,
    hint: '最近状态仍为执行中的任务',
  },
  {
    label: '失败任务',
    value: syncState.value.filter((item) => item.last_status === 'failed').length,
    hint: '最近一次执行失败的任务',
  },
  {
    label: '失败接口调用',
    value: failedApiCount.value,
    hint: '最近 24 小时失败调用累计次数',
  },
])

const keyJobs = computed<JobViewModel[]>(() =>
  keyJobDefinitions.map((definition) => {
    const row = syncState.value.find((item) => item.job_name === definition.jobName)
    return {
      ...definition,
      status: getSyncStatusMeta(row?.last_status),
      lastRunAt: formatTime(row?.last_run_at),
      lastSuccessAt: formatTime(row?.last_success_at),
    }
  }),
)

const autoJobs = computed<JobViewModel[]>(() =>
  autoSyncDefinitions.map((definition) => {
    const row = syncState.value.find((item) => item.job_name === definition.jobName)
    return {
      ...definition,
      status: getSyncStatusMeta(row?.last_status),
      lastRunAt: formatTime(row?.last_run_at),
      lastSuccessAt: formatTime(row?.last_success_at),
    }
  }),
)

function formatTime(value?: string | null): string {
  return value ? dayjs(value).format('MM-DD HH:mm:ss') : '暂无记录'
}

async function reloadAll(): Promise<void> {
  const [syncResult, overviewResult, recentResult] = await Promise.allSettled([
    listSyncState(),
    getApiCallsOverview(24),
    getRecentCalls({ only_failed: true, limit: 10 }),
  ])

  if (syncResult.status === 'fulfilled') {
    syncState.value = syncResult.value
  }
  if (overviewResult.status === 'fulfilled') {
    failedApiCount.value = overviewResult.value.endpoints.reduce(
      (sum, endpoint) => sum + endpoint.failed_count,
      0,
    )
  }
  if (recentResult.status === 'fulfilled') {
    failedCalls.value = recentResult.value
  }
}

onMounted(reloadAll)
</script>

<style lang="scss" scoped>
.sync-overview-view {
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

.metric-grid,
.content-grid {
  display: grid;
  gap: $space-4;
}

.metric-grid {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

.content-grid {
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
}

.metric-label,
.job-meta,
.job-time {
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.metric-value {
  margin-top: $space-2;
  font-size: 28px;
  font-weight: $font-weight-semibold;
}

.metric-hint {
  margin-top: $space-2;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}

.job-list {
  display: flex;
  flex-direction: column;
  gap: $space-3;
}

.job-item {
  display: flex;
  justify-content: space-between;
  gap: $space-4;
  align-items: center;
  padding: $space-3 $space-4;
  border-radius: $radius-lg;
  background: $color-bg-subtle;
  border: 1px solid $color-border-default;
}

.job-title {
  font-weight: $font-weight-semibold;
}

.job-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: $space-2;
  flex-shrink: 0;
}

@media (max-width: 900px) {
  .intro-card,
  .job-item {
    flex-direction: column;
    align-items: flex-start;
  }

  .job-right {
    align-items: flex-start;
  }
}
</style>
