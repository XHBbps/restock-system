<template>
  <div class="suggestion-list">
    <PageSectionCard title="采补发起">
      <template #actions>
        <el-tag v-if="suggestion" :type="statusMeta.tagType" size="small">
          {{ statusMeta.label }} · 采购 {{ suggestion.procurement_item_count }} · 补货 {{ suggestion.restock_item_count }}
        </el-tag>
        <el-tag v-if="currentDemandDate" type="warning" size="small">
          需求截止日期：{{ currentDemandDate }}
        </el-tag>
        <el-tag
          v-if="toggle"
          :type="toggle.enabled ? 'success' : 'info'"
          size="small"
          :title="toggleTitle"
        >
          生成开关：{{ toggle.enabled ? '开启' : '已关闭' }}
        </el-tag>
        <el-date-picker
          v-model="demandDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="需求截止日期"
          :clearable="true"
          :disabled="isEngineBusy"
          class="demand-date-picker"
        />
        <el-button
          v-if="auth.hasPermission('restock:operate')"
          type="primary"
          :loading="generating"
          :disabled="!toggle?.enabled || generating || genTaskId !== null"
          :title="engineButtonTitle"
          @click="triggerEngine"
        >
          生成采补建议
        </el-button>
        <el-button
          v-if="canDelete"
          type="danger"
          plain
          :loading="deleting"
          @click="handleDelete"
        >
          删除整单
        </el-button>
      </template>

      <TaskProgress v-if="genTaskId" :task-id="genTaskId" @terminal="onGenDone" />

      <el-empty
        v-if="!loading && !suggestion"
        description="当前没有活动建议单，点击上方按钮生成采补建议。"
        :image-size="80"
      />

      <template v-else>
        <SuggestionTabBar base-path="/restock/current" />
        <router-view v-slot="{ Component }">
          <component
            :is="Component"
            :suggestion="suggestion"
            :items="suggestion?.items ?? []"
            :loading="loading"
            @refresh="loadCurrent"
          />
        </router-view>
      </template>
    </PageSectionCard>
  </div>
</template>

<script setup lang="ts">
import { runEngine } from '@/api/engine'
import { listTasks, type TaskRun } from '@/api/task'
import {
  getGenerationToggle,
  patchGenerationToggle,
  type GenerationToggle,
} from '@/api/config'
import { deleteSuggestion, getCurrentSuggestion, type SuggestionDetail } from '@/api/suggestion'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SuggestionTabBar from '@/components/SuggestionTabBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { getSuggestionDisplayStatusMeta } from '@/utils/status'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onActivated, onMounted, ref } from 'vue'

const auth = useAuthStore()
const suggestion = ref<SuggestionDetail | null>(null)
const generating = ref(false)
const deleting = ref(false)
const genTaskId = ref<number | null>(null)
const loading = ref(false)
const demandDate = ref('')

const canDelete = computed(() => {
  const sug = suggestion.value
  if (!sug || sug.status !== 'draft') return false
  return (sug.procurement_snapshot_count || 0) + (sug.restock_snapshot_count || 0) === 0
})

async function handleDelete(): Promise<void> {
  const currentSuggestion = suggestion.value
  if (!currentSuggestion) return
  try {
    await ElMessageBox.confirm(
      '删除后无法恢复，且会同时移除采购和补货视图（采补同属一个建议单）。确定删除？',
      '确认删除整个采补建议单',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  deleting.value = true
  try {
    await deleteSuggestion(currentSuggestion.id)
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '删除失败'))
    deleting.value = false
    return
  }

  try {
    await patchGenerationToggle(true)
    ElMessage.success('删除成功，已自动开启生成开关')
  } catch (error) {
    ElMessage.warning(
      getActionErrorMessage(
        error,
        '删除成功，但开启生成开关失败，请前往全局参数手动开启',
      ),
    )
  } finally {
    await loadCurrent()
    await loadToggle()
    deleting.value = false
  }
}

const toggle = ref<GenerationToggle | null>(null)
const toggleLoadError = ref(false)

const totalSnapshotCount = computed(
  () =>
    (suggestion.value?.procurement_snapshot_count ?? 0) +
    (suggestion.value?.restock_snapshot_count ?? 0),
)

const isEngineBusy = computed(() => generating.value || genTaskId.value !== null)

const currentDemandDate = computed(() => {
  const value = suggestion.value?.global_config_snapshot?.demand_date
  return typeof value === 'string' && value ? value : ''
})

const toggleTitle = computed(() => {
  if (!toggle.value) return ''
  const by = toggle.value.updated_by_name ?? '—'
  const at = toggle.value.updated_at ?? '—'
  return `最近操作：${by} @ ${at}`
})

const engineButtonTitle = computed(() => {
  if (toggleLoadError.value || toggle.value === null) {
    return '无法确认生成开关状态，请刷新页面或检查权限'
  }
  if (!toggle.value.enabled) {
    return '生成开关已关闭，请先在「全局参数」中开启'
  }
  if (genTaskId.value !== null) {
    return '已有采补生成任务在运行，请等待任务完成'
  }
  return ''
})

const statusMeta = computed(() =>
  suggestion.value
    ? getSuggestionDisplayStatusMeta(suggestion.value.status, totalSnapshotCount.value)
    : { label: '暂无', tagType: 'info' as const },
)

async function loadCurrent(): Promise<void> {
  loading.value = true
  try {
    suggestion.value = await getCurrentSuggestion()
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
    } else {
      ElMessage.error(getActionErrorMessage(err, '加载当前建议失败'))
    }
  } finally {
    loading.value = false
  }
}

async function triggerEngine(): Promise<void> {
  const selectedDemandDate = demandDate.value
  if (!selectedDemandDate) {
    ElMessage.warning('请选择需求截止日期')
    return
  }
  if (selectedDemandDate < getBeijingTodayText()) {
    ElMessage.warning('需求截止日期不能早于今天')
    return
  }

  generating.value = true
  try {
    const { data } = await runEngine({ demand_date: selectedDemandDate })
    genTaskId.value = data.task_id
    if (data.existing) {
      ElMessage.warning('已有规则引擎任务在运行，当前复用现有任务进度')
    } else {
      ElMessage.success('规则引擎任务已入队')
    }
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '采补任务触发失败'))
  } finally {
    generating.value = false
  }
}

async function onGenDone(task: TaskRun): Promise<void> {
  genTaskId.value = null
  await loadCurrent()
  await loadToggle()
  if (task.status === 'success') {
    demandDate.value = ''
    ElMessage.success('采补任务已完成，当前建议已刷新')
    return
  }
  ElMessage.error(task.error_msg || '采补任务执行失败，请查看任务详情')
}

async function loadActiveEngineTask(): Promise<void> {
  try {
    const [pending, running] = await Promise.all([
      listTasks({ job_name: 'calc_engine', status: 'pending', limit: 1 }),
      listTasks({ job_name: 'calc_engine', status: 'running', limit: 1 }),
    ])
    const activeTask = running.items[0] ?? pending.items[0] ?? null
    genTaskId.value = activeTask?.id ?? null
  } catch {
    // 无权限或网络错误时保持当前页面状态，不阻断建议单展示。
  }
}

function getBeijingTodayText(): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const getPart = (type: string) => parts.find((part) => part.type === type)?.value ?? ''
  return `${getPart('year')}-${getPart('month')}-${getPart('day')}`
}

async function loadToggle(): Promise<void> {
  try {
    toggle.value = await getGenerationToggle()
    toggleLoadError.value = false
  } catch {
    toggle.value = null
    toggleLoadError.value = true
  }
}

onMounted(() => {
  void loadCurrent()
  void loadToggle()
  void loadActiveEngineTask()
})

onActivated(() => {
  void loadToggle()
  void loadActiveEngineTask()
})
</script>

<style lang="scss" scoped>
.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: $space-4;
}

.demand-date-picker {
  width: 150px;
}
</style>
