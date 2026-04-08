<template>
  <div class="api-monitor">
    <el-alert
      v-if="overview && overview.postal_compliance_warning > 0"
      type="warning"
      :title="`⚠ ${overview.postal_compliance_warning} 单订单已超过 50 天未拉取邮编（接近 60 天屏蔽窗口）`"
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="card-title">赛狐接口监控（最近 24 小时）</span>
          <el-button @click="reload">刷新</el-button>
        </div>
      </template>

      <div class="endpoint-grid" v-loading="loading">
        <div
          v-for="ep in overview?.endpoints || []"
          :key="ep.endpoint"
          class="endpoint-card"
        >
          <div class="endpoint-header">
            <div class="endpoint-name" :title="ep.endpoint">{{ shortName(ep.endpoint) }}</div>
            <el-tag :type="ep.success_rate >= 0.99 ? 'success' : ep.success_rate >= 0.9 ? 'warning' : 'danger'">
              {{ (ep.success_rate * 100).toFixed(0) }}%
            </el-tag>
          </div>
          <div class="endpoint-stats">
            <div>
              <span class="stat-label">总调用</span>
              <strong>{{ ep.total_calls }}</strong>
            </div>
            <div>
              <span class="stat-label">成功</span>
              <strong style="color: #2d7a6a">{{ ep.success_count }}</strong>
            </div>
            <div>
              <span class="stat-label">失败</span>
              <strong style="color: #e35d6a">{{ ep.failed_count }}</strong>
            </div>
          </div>
          <div class="endpoint-meta">
            最近: {{ ep.last_called_at ? formatTime(ep.last_called_at) : '-' }}
          </div>
          <div v-if="ep.last_error" class="endpoint-error" :title="ep.last_error">
            ❌ {{ ep.last_error }}
          </div>
        </div>
        <div v-if="!overview?.endpoints?.length" class="empty">
          暂无调用记录
        </div>
      </div>
    </el-card>

    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span class="card-title">最近失败调用</span>
          <div class="actions">
            <el-switch v-model="onlyFailed" active-text="仅失败" @change="loadRecent" />
          </div>
        </div>
      </template>

      <el-table :data="recentCalls" v-loading="recentLoading">
        <el-table-column label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.called_at) }}
          </template>
        </el-table-column>
        <el-table-column label="接口" min-width="320">
          <template #default="{ row }">
            <code>{{ row.endpoint }}</code>
          </template>
        </el-table-column>
        <el-table-column label="耗时(ms)" prop="duration_ms" width="100" align="right" />
        <el-table-column label="HTTP" prop="http_status" width="80" align="center" />
        <el-table-column label="赛狐 code" prop="saihu_code" width="100" align="center" />
        <el-table-column label="错误信息" min-width="200">
          <template #default="{ row }">
            <span v-if="row.saihu_msg" class="error-msg">{{ row.saihu_msg }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.saihu_code !== 0"
              link
              type="primary"
              @click="retry(row)"
            >
              重试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <TaskProgress v-if="retryTaskId" :task-id="retryTaskId" @terminal="retryTaskId = null" />
  </div>
</template>

<script setup lang="ts">
import {
  getApiCallsOverview,
  getRecentCalls,
  retryCall,
  type ApiCallsOverview,
  type RecentCall
} from '@/api/monitor'
import TaskProgress from '@/components/TaskProgress.vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

const overview = ref<ApiCallsOverview | null>(null)
const recentCalls = ref<RecentCall[]>([])
const loading = ref(false)
const recentLoading = ref(false)
const onlyFailed = ref(true)
const retryTaskId = ref<number | null>(null)

async function reload(): Promise<void> {
  loading.value = true
  try {
    overview.value = await getApiCallsOverview(24)
  } finally {
    loading.value = false
  }
  await loadRecent()
}

async function loadRecent(): Promise<void> {
  recentLoading.value = true
  try {
    recentCalls.value = await getRecentCalls({ only_failed: onlyFailed.value, limit: 50 })
  } finally {
    recentLoading.value = false
  }
}

function shortName(endpoint: string): string {
  const parts = endpoint.split('/')
  return parts[parts.length - 1] || endpoint
}

function formatTime(t: string): string {
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

async function retry(row: RecentCall): Promise<void> {
  try {
    const resp = await retryCall(row.id)
    if (resp.task_id) {
      retryTaskId.value = resp.task_id
      ElMessage.success('已入队重试')
    } else {
      ElMessage.warning('该接口不支持自动重试')
    }
  } catch {
    ElMessage.error('重试失败')
  }
}

onMounted(reload)
</script>

<style lang="scss" scoped>
.api-monitor {
  display: flex;
  flex-direction: column;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: $font-size-lg;
  font-weight: $font-weight-semibold;
}
.endpoint-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: $space-4;
}
.endpoint-card {
  background: $color-bg-subtle;
  border-radius: $radius-lg;
  padding: $space-4;
}
.endpoint-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: $space-3;
  .endpoint-name {
    font-weight: $font-weight-medium;
    font-size: $font-size-sm;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
.endpoint-stats {
  display: flex;
  gap: $space-4;
  margin-bottom: $space-3;
  .stat-label {
    display: block;
    color: $color-text-secondary;
    font-size: $font-size-xs;
  }
  strong {
    font-size: $font-size-lg;
  }
}
.endpoint-meta {
  font-size: $font-size-xs;
  color: $color-text-secondary;
}
.endpoint-error {
  margin-top: $space-2;
  font-size: $font-size-xs;
  color: $color-danger;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.empty {
  text-align: center;
  padding: $space-8;
  color: $color-text-secondary;
}
.error-msg {
  color: $color-danger;
  font-size: $font-size-xs;
}
</style>
