// 任务进度轮询 store
import { getTask, type TaskRun } from '@/api/task'
import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'

const POLL_INTERVAL_MS = 2000
const MAX_RETRY = 3
const TERMINAL_STATES = new Set(['success', 'failed', 'skipped', 'cancelled'])

export const useTaskStore = defineStore('task', () => {
  const tasksById = reactive<Record<number, TaskRun>>({})
  const polling = ref<Set<number>>(new Set())
  const networkErrors = reactive<Record<number, string>>({})
  const _retryCount: Record<number, number> = {}

  function isTerminal(task: TaskRun): boolean {
    return TERMINAL_STATES.has(task.status)
  }

  async function startPolling(taskId: number, onTerminal?: (t: TaskRun) => void): Promise<void> {
    if (polling.value.has(taskId)) return
    polling.value.add(taskId)
    _retryCount[taskId] = 0
    delete networkErrors[taskId]

    const tick = async () => {
      if (!polling.value.has(taskId)) return
      try {
        const t = await getTask(taskId)
        if (!polling.value.has(taskId)) return
        tasksById[taskId] = t
        _retryCount[taskId] = 0
        delete networkErrors[taskId]
        if (isTerminal(t)) {
          polling.value.delete(taskId)
          delete _retryCount[taskId]
          onTerminal?.(t)
          return
        }
      } catch {
        _retryCount[taskId] = (_retryCount[taskId] || 0) + 1
        if (_retryCount[taskId] >= MAX_RETRY) {
          polling.value.delete(taskId)
          networkErrors[taskId] = '网络异常，请刷新页面查看任务状态'
          delete _retryCount[taskId]
          return
        }
        // 指数退避重试：2s, 4s
        const delay = POLL_INTERVAL_MS * Math.pow(2, _retryCount[taskId] - 1)
        setTimeout(tick, delay)
        return
      }
      setTimeout(tick, POLL_INTERVAL_MS)
    }
    tick()
  }

  function stopPolling(taskId: number): void {
    polling.value.delete(taskId)
  }

  return { tasksById, polling, networkErrors, startPolling, stopPolling, isTerminal }
})
