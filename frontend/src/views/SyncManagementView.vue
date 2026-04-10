<template>
  <div class="sync-mgmt">
    <!-- 邮编合规警告 -->
    <el-alert
      v-if="overview && overview.postal_compliance_warning > 0"
      type="warning"
      :title="`⚠ ${overview.postal_compliance_warning} 单订单已超过 50 天未拉取邮编（接近 60 天屏蔽窗口）`"
      :closable="false"
    />

    <!-- 触发操作 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div class="title-block">
            <span class="card-title">触发操作</span>
            <span class="card-meta">手动触发同步与规则引擎</span>
          </div>
          <el-button @click="reloadAll">刷新全部数据</el-button>
        </div>
      </template>

      <div class="action-grid">
        <div v-for="action in actions" :key="action.key" class="action-card">
          <div class="action-info">
            <h3>{{ action.label }}</h3>
            <p>{{ action.desc }}</p>
          </div>
          <el-button
            type="primary"
            :loading="loadingActions[action.key] || false"
            @click="trigger(action)"
          >
            执行
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 当前运行任务 -->
    <TaskProgress
      v-if="currentTaskId"
      :task-id="currentTaskId"
      @terminal="onTaskDone"
    />

    <!-- sync_state 状态表 -->
    <el-card shadow="never">
      <template #header>
        <div class="title-block">
          <span class="card-title">各同步任务状态</span>
          <span class="card-meta">sync_state 表 · 记录每个 job 的最近一次成功时间与错误</span>
        </div>
      </template>
      <el-table v-loading="loadingSyncState" :data="syncState">
        <el-table-column label="任务名称" prop="job_name" min-width="200" sortable show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.job_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近运行" width="180" sortable show-overflow-tooltip>
          <template #default="{ row }">
            <span class="muted mono">{{ row.last_run_at ? formatTime(row.last_run_at) : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近成功" width="180" sortable show-overflow-tooltip>
          <template #default="{ row }">
            <span class="muted mono">{{ row.last_success_at ? formatTime(row.last_success_at) : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120" sortable>
          <template #default="{ row }">
            <el-tag v-if="row.last_status === 'success'" type="success" size="small">success</el-tag>
            <el-tag v-else-if="row.last_status === 'failed'" type="danger" size="small">failed</el-tag>
            <el-tag v-else-if="row.last_status === 'running'" type="warning" size="small">running</el-tag>
            <el-tag v-else type="info" size="small">{{ row.last_status || '从未运行' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="错误信息" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.last_error" class="error-text">{{ row.last_error }}</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 接口监控卡片网格 -->
    <el-card shadow="never">
      <template #header>
        <div class="title-block">
          <span class="card-title">接口监控（近 24h）</span>
          <span class="card-meta">api_call_log · 每次外部接口调用的结果聚合</span>
        </div>
      </template>
      <div v-loading="loadingOverview" class="endpoint-grid">
        <div v-for="ep in overview?.endpoints || []" :key="ep.endpoint" class="endpoint-card">
          <div class="endpoint-header">
            <div class="endpoint-name" :title="ep.endpoint">{{ shortName(ep.endpoint) }}</div>
            <el-tag :type="rateTag(ep.success_rate)" size="small">
              {{ (ep.success_rate * 100).toFixed(0) }}%
            </el-tag>
          </div>
          <div class="endpoint-stats">
            <div><span class="stat-label">总调用</span><strong>{{ ep.total_calls }}</strong></div>
            <div><span class="stat-label">成功</span><strong class="success">{{ ep.success_count }}</strong></div>
            <div><span class="stat-label">失败</span><strong class="danger">{{ ep.failed_count }}</strong></div>
          </div>
          <div class="endpoint-meta">
            最近: {{ ep.last_called_at ? formatTime(ep.last_called_at) : '—' }}
          </div>
          <div v-if="ep.last_error" class="endpoint-error" :title="ep.last_error">❌ {{ ep.last_error }}</div>
        </div>
        <div v-if="!overview?.endpoints?.length" class="empty">暂无调用记录</div>
      </div>
    </el-card>

    <!-- 最近失败调用 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div class="title-block">
            <span class="card-title">最近调用记录</span>
            <span class="card-meta">可手动重试失败的 sync 任务</span>
          </div>
          <el-switch v-model="onlyFailed" active-text="仅失败" @change="loadRecent" />
        </div>
      </template>
      <el-table v-loading="loadingRecent" :data="recentCalls">
        <el-table-column label="时间" width="170" sortable>
          <template #default="{ row }"><span class="mono muted">{{ formatTime(row.called_at) }}</span></template>
        </el-table-column>
        <el-table-column label="接口" min-width="320">
          <template #default="{ row }"><code class="mono">{{ row.endpoint }}</code></template>
        </el-table-column>
        <el-table-column label="耗时(ms)" prop="duration_ms" width="100" align="right" sortable show-overflow-tooltip />
        <el-table-column label="HTTP状态" prop="http_status" width="90" align="center" sortable show-overflow-tooltip />
        <el-table-column label="平台代码" prop="saihu_code" width="110" align="center" sortable show-overflow-tooltip />
        <el-table-column label="错误信息" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.saihu_msg" class="error-text">{{ row.saihu_msg }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="{ row }">
            <el-button v-if="row.saihu_code !== 0" link type="primary" @click="retry(row)">重试</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import client from '@/api/client'
import { listSyncState, type SyncStateRow } from '@/api/data'
import {
  getApiCallsOverview,
  getRecentCalls,
  retryCall,
  type ApiCallsOverview,
  type RecentCall
} from '@/api/monitor'
import TaskProgress from '@/components/TaskProgress.vue'
import type { TagType } from '@/utils/element'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

interface Action {
  key: string
  label: string
  desc: string
  url: string
}

const actions: Action[] = [
  { key: 'all', label: '全量同步', desc: '按顺序触发所有同步任务', url: '/api/sync/all' },
  { key: 'product', label: '在线产品信息', desc: 'match=true + commodity_id 映射', url: '/api/sync/product-listing' },
  { key: 'warehouse', label: '仓库列表', desc: '仓库主数据', url: '/api/sync/warehouse' },
  { key: 'inventory', label: '库存明细', desc: '可用 + 占用（跳过 stockWait）', url: '/api/sync/inventory' },
  { key: 'transit', label: '其他出库', desc: '在途数据（备注含"在途中"）', url: '/api/sync/out-records' },
  { key: 'orders', label: '订单', desc: '列表 + 已配对 SKU 详情', url: '/api/sync/orders' },
  { key: 'engine', label: '规则引擎', desc: '生成新建议单（归档旧单）', url: '/api/engine/run' }
]

const loadingActions = reactive<Record<string, boolean>>({})
const currentTaskId = ref<number | null>(null)

const overview = ref<ApiCallsOverview | null>(null)
const loadingOverview = ref(false)
const recentCalls = ref<RecentCall[]>([])
const loadingRecent = ref(false)
const onlyFailed = ref(true)
const syncState = ref<SyncStateRow[]>([])
const loadingSyncState = ref(false)

async function trigger(action: Action): Promise<void> {
  loadingActions[action.key] = true
  try {
    const { data } = await client.post<{ task_id: number; existing: boolean }>(action.url)
    currentTaskId.value = data.task_id
    if (data.existing) ElMessage.warning('已有同名任务在运行，复用其进度')
    else ElMessage.success('任务已入队')
  } catch {
    ElMessage.error('任务触发失败')
  } finally {
    loadingActions[action.key] = false
  }
}

function onTaskDone(): void {
  ElMessage.info('任务完成')
  currentTaskId.value = null
  reloadAll()
}

async function loadOverview(): Promise<void> {
  loadingOverview.value = true
  try {
    overview.value = await getApiCallsOverview(24)
  } finally {
    loadingOverview.value = false
  }
}

async function loadRecent(): Promise<void> {
  loadingRecent.value = true
  try {
    recentCalls.value = await getRecentCalls({ only_failed: onlyFailed.value, limit: 50 })
  } finally {
    loadingRecent.value = false
  }
}

async function loadSyncState(): Promise<void> {
  loadingSyncState.value = true
  try {
    syncState.value = await listSyncState()
  } finally {
    loadingSyncState.value = false
  }
}

async function reloadAll(): Promise<void> {
  // allSettled 保证一个 loader 失败不会让其余已完成结果被丢弃
  await Promise.allSettled([loadOverview(), loadRecent(), loadSyncState()])
}

async function retry(row: RecentCall): Promise<void> {
  try {
    const resp = await retryCall(row.id)
    if (resp.task_id) {
      currentTaskId.value = resp.task_id
      ElMessage.success('已入队重试')
    } else {
      ElMessage.warning('该接口不支持自动重试')
    }
  } catch {
    ElMessage.error('重试失败')
  }
}

function rateTag(rate: number): TagType {
  if (rate >= 0.99) return 'success'
  if (rate >= 0.9) return 'warning'
  return 'danger'
}

function shortName(endpoint: string): string {
  const parts = endpoint.split('/')
  return parts[parts.length - 1] || endpoint
}

function formatTime(t: string): string {
  return dayjs(t).format('MM-DD HH:mm:ss')
}

onMounted(reloadAll)
</script>

<style lang="scss" scoped>
.sync-mgmt {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title-block {
  display: flex;
  flex-direction: column;
}
.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
  letter-spacing: $tracking-tight;
}
.card-meta {
  font-size: $font-size-xs;
  color: $color-text-secondary;
  font-family: $font-family-mono;
  margin-top: 2px;
}
.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: $space-4;
}
.action-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: $color-bg-subtle;
  border-radius: $radius-lg;
  padding: $space-4 $space-5;
  border: 1px solid $color-border-default;

  .action-info {
    h3 {
      margin: 0 0 $space-1 0;
      font-size: $font-size-sm;
      font-weight: $font-weight-semibold;
      letter-spacing: $tracking-tight;
    }
    p {
      margin: 0;
      color: $color-text-secondary;
      font-size: $font-size-xs;
    }
  }
}
.endpoint-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: $space-4;
}
.endpoint-card {
  background: $color-bg-subtle;
  border: 1px solid $color-border-default;
  border-radius: $radius-lg;
  padding: $space-4;
}
.endpoint-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-3;
  .endpoint-name {
    font-size: $font-size-xs;
    font-weight: $font-weight-semibold;
    font-family: $font-family-mono;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}
.endpoint-stats {
  display: flex;
  gap: $space-4;
  margin-bottom: $space-2;
  .stat-label {
    display: block;
    color: $color-text-secondary;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: $tracking-wider;
  }
  strong {
    font-size: $font-size-lg;
    font-weight: $font-weight-semibold;
  }
  .success {
    color: $color-success;
  }
  .danger {
    color: $color-danger;
  }
}
.endpoint-meta {
  font-size: 11px;
  color: $color-text-secondary;
  font-family: $font-family-mono;
}
.endpoint-error {
  margin-top: $space-2;
  font-size: 11px;
  color: $color-danger;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty {
  text-align: center;
  padding: $space-8;
  color: $color-text-secondary;
  grid-column: 1 / -1;
}
.muted {
  color: $color-text-secondary;
}
.mono {
  font-family: $font-family-mono;
  font-size: $font-size-xs;
}
.error-text {
  color: $color-danger;
  font-size: $font-size-xs;
}
</style>
